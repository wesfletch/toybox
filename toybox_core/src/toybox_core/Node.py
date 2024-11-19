#!/usr/bin/env python3

import atexit
from queue import Queue, Empty
import select
import socket
import threading
import time
from typing import Dict, List, Union, Tuple, Callable, Optional

import grpc
from google.protobuf.message import Message, DecodeError
import concurrent.futures as futures

from toybox_core.Connection import (
    Connection,
    Subscriber,
    Publisher,
    get_available_port,
)

import toybox_msgs.core.Register_pb2 as Register_pb2
from toybox_core.TopicServer import subscribe_topic_rpc

from toybox_core.ClientServer import ClientRPCServicer
from toybox_msgs.core.Client_pb2_grpc import add_ClientServicer_to_server
import toybox_msgs.core.Topic_pb2 as Topic_pb2
from toybox_core.Logging import TbxLogger

class Node():

    def __init__(
        self,
        name: str,
        host: str = "localhost",
        port: Optional[int] = None,
        log_level: Optional[str] = None,
    ) -> None:

        self._name = name
        self._host: str = host
        self._port: int = port if port else get_available_port()

        # configure logger
        self._logger: TbxLogger = TbxLogger(self._name)
        if log_level:
            self.set_log_level(log_level=log_level)

        # thread management
        self._shutdown: bool = False

        # queue of messages for inbound and outbound connections
        self._connections: Dict[socket.socket, Connection] = {}
        self._conn_lock: threading.Lock = threading.Lock()
        
        # inbound topics
        self._subscribers: List[Subscriber] = []
        self._subscribers_lock: threading.Lock = threading.Lock()

        # outbound topics
        self._publishers: List[Publisher] = []
        self._publishers_lock: threading.Lock = threading.Lock()

        # open socket for message-passing between clients
        self._msg_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        self._msg_port = get_available_port(host=self._host, start=self._port+1)
        self._msg_socket.bind((self._host, self._msg_port))

        # listen for incoming connections in separate thread
        self.listen_thread: threading.Thread = threading.Thread(target=self._listen)
        self.listen_thread.start()

        # run our spin function as a separate thread
        self.spin_thread: threading.Thread = threading.Thread(target=self._spin)
        self.spin_thread.start()

        self._threads: List[threading.Thread] = []

        self._executor: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(
            max_workers=10
        )
        self._configure_rpc_servicer()

        atexit.register(self.shutdown)

    def shutdown(self) -> None:
        self._shutdown = True
        # deregister_client_rpc(self._name)

    def is_shutdown(self) -> bool:
        return self._shutdown

    def _configure_rpc_servicer(self) -> None:
        """
        Create the RPC server that we'll use to field RPCs from other clients.
        """

        self._rpc_server: grpc.server = grpc.server(
            thread_pool=self._executor,
        )
        add_ClientServicer_to_server(
            servicer=ClientRPCServicer(
                subscribers=self._subscribers, 
            ),
            server=self._rpc_server,
        )

        self._rpc_server.add_insecure_port(f'[::]:{self._port}')

        # non-blocking
        self._rpc_server.start()

    def _listen(self) -> None:
        """
        Listen for "ephemeral" connections to this Node from other Nodes.
        Ephemeral connections either go away quickly, or are transitioned to Subs/Pubs.
        """

        # enable socket to accept connections
        self._msg_socket.listen()
        # make socket non-blocking
        self._msg_socket.settimeout(0)

        # listen for new connections to add to list
        while not self._shutdown:
            try:
                conn, addr = self._msg_socket.accept()
                self.log("DEBUG", f"<{self._name}> accepted conn request from {conn.getpeername()}")
                with self._conn_lock:                
                    self._connections[conn] = Connection(
                        name="",
                        sock=conn,
                        host=addr[0],
                        port=addr[1],
                    )
            except BlockingIOError:
                time.sleep(0.01)

        self._msg_socket.shutdown(socket.SHUT_RDWR)
        self._msg_socket.close()

    def _spin_once(self) -> None:
        """
        Message-handling loop. One-shot.
        """

        ready_to_read: List[socket.socket] = []
        ready_to_write: List[socket.socket] = []

        # acquire the "connection" mutex to ensure we don't read the list while it's changing
        if not self._conn_lock.acquire(blocking=False):
            return

        # get available [in/out]bound sockets
        connections: List[socket.socket] = self._connections.keys() 
        ready_to_read, ready_to_write, _ = select.select(
            connections, 
            connections, 
            [], 0)
        self._conn_lock.release()

        message: bytes

        # TODO: I've somehow turned this whole block into dead code??? Figure that out.
        for conn in ready_to_read:
            message = self._connections[conn].read(conn=conn)
            self._handle_message(conn=conn, message=message)

        for conn in ready_to_write:
            connection: Connection | None = self.connections.get(conn, None)
            if connection is None:
                # connection might have been deleted by another thread
                continue
            elif not connection.initialized:
                # we can't trust un-initialized connections to behave
                continue

            try:
                message = self._connections[conn].outbound.get(block=False)
            except Empty:
                continue

            self.log("DEBUG", f"<{self._name}> sent message to {self._connections[conn].name}: {message}")
            self._connections[conn].sock.sendall(message)


    def _spin(self) -> None:
        """
        Message-handling loop.
        """
        
        # service ephemeral connections
        while not self._shutdown:
            
            # TODO: need this to avoid all sorts of weird messaging order issues,
            #       should probably figure out why
            time.sleep(0.01)
            
            self._spin_once()


    def _handle_message(
        self, 
        conn: socket.socket, 
        message: bytes,
    ) -> None:
        """
        Handle messages that come in from TBX servers or other nodes for the management
        of this Node, e.g., introductions from other nodes.

        TODO: awaiting refactor... Does this function even get called anymore? How on earth is this
                still working?

        Args:
            conn (socket.socket): _description_
            message (bytes): _description_
        """

        # TODO: this isn't even correct anymore... What is going on here?
        message_type, message_data = Connection.split_message(message)

        self.log("DEBUG",f'<{self._name}> received: \n\tmessage_type=<{message_type}>\n\tmessage={message_data!r}')

        # TODO: these should really be broken out into callbacks
        if message_type == "core.ClientInfo":
            # this is another client introducing themselves
            client_info: Register_pb2.ClientInfo = Register_pb2.ClientInfo()
            try:
                client_info.ParseFromString(message_data)
            except DecodeError as e:
                self.log("ERR", f"We just got garbage: {e}")
                return
            
            if not self._connections[conn].initialized:
                self.log("DEBUG", f"{self._name} initializing connection with {client_info.client_id}")
                self._connections[conn].name = client_info.client_id
                self._connections[conn].initialized = True
            else:
                self.log("DEBUG", "already initialized")
                return
            
        elif message_type == "core.Confirmation":
            
            confirmation: Topic_pb2.Confirmation = Topic_pb2.Confirmation()
            try:
                confirmation.ParseFromString(message_data)
            except DecodeError as e:
                self.log("ERR", f"We just got garbage: {e}")
                return
            
            self.log("DEBUG", f"{self._name}: {confirmation}")

        else:
            self.log("DEBUG", f"Got unhandled message type: <{message_type}>")
            # messages that aren't explicitly handled just go into the inbound queues
            self._connections[conn].inbound.put(message.decode('utf-8'))

    def _configure_publisher(
        self, 
        topic_name: str, 
        message_type: str
    ) -> Publisher:

        # create a publisher, 
        # REMEMBER: PUblishers don't connect().
        publisher: Publisher = Publisher(
            topic_name=topic_name,
            message_type=message_type,
            host=self._host,
            port=get_available_port(host=self._host, start=self._msg_port),
            logger=self._logger
        )

        return publisher

    def _configure_subscriber(
        self, 
        topic_name: str, 
        message_type: Message, 
        publisher_info: Tuple[str,str,int] | None,
        callback: Union[Callable, None] = None,
    ) -> Subscriber:

        subscriber: Subscriber = Subscriber(
            topic_name=topic_name,
            message_type=message_type,
            host=self._host,
            port=get_available_port(host=self._host, start=self._msg_port),
            publisher_info=publisher_info,
            callback=callback,
            logger=self._logger
        )

        self.subscribers.append(subscriber)
        return subscriber

    def advertise(
        self,
        topic_name: str,
        message_type: Message
    ) -> Publisher | None:
        """
        Advertise a topic that this Node plans to publish.

        Args:
            topic_name (str): The name of the topic
            message_type (Message): The message type of the topic

        Returns:
            PUblisher | None : If the topic was advertised properly, returns the Publisher, \
                                   otherwise returns None
        """

        pub: Publisher = self._configure_publisher(
            topic_name=topic_name,
            message_type=message_type,
        )
        # TODO: see body of _configure_publisher, this doesn't make any sense. 
        # Why am I appending to 
        if not pub.advertise(advertiser_id=self._name):
            self.log("ERR", f"Failed to advertise topic <{topic_name}>")
            return None
        
        self.log("DEBUG", f"Successfully advertised topic <{topic_name}> with message type <{message_type.DESCRIPTOR.full_name}>")
        
        self.publishers.append(pub)
        return pub

    def subscribe(
        self,
        topic_name: str,
        message_type: Message,
        callback_fn: Optional[Callable] = None
    ) -> bool:
    
        # request information about publishers of a specific topic
        self.log("DEBUG", f"{self._name} requesting topic information")
        try:
            publishers: List[Tuple[str, int]] = subscribe_topic_rpc(
                topic_name=topic_name,
                message_type=message_type.DESCRIPTOR.full_name)
        except grpc.RpcError as rpc_error:
            self.log("ERR", f"that didn't work: {rpc_error}")
            return False
        
        if len(publishers) == 0:
            self.log("DEBUG", f"no publishers declared for topic <{topic_name}>")
            self._configure_subscriber(
                topic_name=topic_name,
                message_type=message_type,
                publisher_info=None,
                callback=callback_fn,
            )
        else:
            self.log("DEBUG", f"At least one publisher for topic <{topic_name}>")
            for publisher in publishers:
                self.log("DEBUG", f"Subscribing to <{topic_name}> from publisher <{publisher[0]}>")
                self._configure_subscriber(
                    topic_name=topic_name,
                    message_type=message_type,
                    publisher_info=publisher,
                    callback=callback_fn,
                )

        return True
    
    def log(
        self,
        log_level: str,
        message: str
    ) -> None:
        self._logger.LOG(log_level=log_level, message=message)

    def set_log_level(
        self,
        log_level: str
    ) -> None:
        
        try:
            self._logger.set_log_level(log_level=log_level)
        except KeyError as e:
            self.log("ERROR", str(e))
    
    def __str__(self) -> str:
        return self._name

    @property
    def connections(self) -> Dict[socket.socket,Connection]:
        with self._conn_lock:
            return self._connections
    
    @property
    def subscribers(self) -> List[Subscriber]:
        if not self._subscribers_lock.acquire(blocking=False):
            return []
        else:
            subs: List[Subscriber] = self._subscribers
            self._subscribers_lock.release()
            return subs
        
    @property
    def publishers(self) -> List[Publisher]:
        if not self._publishers_lock.acquire(blocking=False):
            return []
        else:
            pubs: List[Publisher] = self._publishers
            self._publishers_lock.release()
            return pubs
        
    def get_connection(self, name: str, blocking: bool = False) -> Union[Connection, None]:
        if blocking:
            while True:
                for conn in self._connections.values():
                    if conn.name == name:
                        return conn
        else:
            for conn in self._connections.values():
                if conn.name == name:
                    return conn
        return None

    def wait_for_connections(self, blocking: bool = True) -> bool:
        """Test synchronization"""
        if blocking:
            while len(self._connections) == 0:
                continue
            return True
        else:
            return len(self._connections) != 0
    
    def wait_for_initialized(self) -> None:
        """Test synchronization"""
        not_initialized: List[Connection] = [x for x in self._connections.values() if not x.initialized]
        while len(not_initialized) != 0:
            with self._conn_lock:
                not_initialized = [x for x in self._connections.values() if not x.initialized]

    def wait_for_subscription(self, topic_name: str) -> None:
        """Test synchronization"""
        while self._subscriptions.get(topic_name, None) is None:
            continue
        while self._subscriptions.get(topic_name, None).confirmed == False:
            continue
