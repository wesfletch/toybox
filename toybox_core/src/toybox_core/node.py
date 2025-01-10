#!/usr/bin/env python3

import atexit
from queue import Queue, Empty
import select
import socket
import threading
import time
from typing import Callable, Dict, List, Tuple

import grpc
from google.protobuf.message import Message
import concurrent.futures as futures

from toybox_core.connection import (
    Connection,
    Subscriber,
    Publisher,
    get_available_port,
)

from toybox_core.rpc.register import deregister_client_rpc, register_client_rpc
from toybox_core.rpc.topic import subscribe_topic_rpc

from toybox_core.logging import TbxLogger
from toybox_core.rpc.client import ClientRPCServicer
from toybox_msgs.core.Client_pb2_grpc import add_ClientServicer_to_server

class Node():

    def __init__(
        self,
        name: str,
        host: str = "localhost",
        port: int | None = None,
        log_level: str | None = None,
        autostart: bool = True
    ) -> None:

        self._name = name
        self._host: str = host
        self._port: int = port if port else get_available_port()

        # configure logger
        self._logger: TbxLogger = TbxLogger(self._name)
        if log_level:
            self.set_log_level(log_level=log_level)

        # The shutdown property allows for Node-holders to trigger a shutdown
        # of this Node.
        self._shutdown: bool = False
        # The shutdown_event allows killing the node from, for example, a ThreadPoolExecutor
        # without calling the explicit shutdown() function.
        self._shutdown_event: threading.Event = threading.Event()

        # queue of messages for inbound and outbound connections
        self._connections: Dict[socket.socket, Connection] = {}
        self._conn_lock: threading.Lock = threading.Lock()
        
        # Subscribers (inbound connections)
        self._subscribers: List[Subscriber] = []
        self._subscribers_lock: threading.Lock = threading.Lock()

        # Publishers (inbound connections)
        self._publishers: List[Publisher] = []
        self._publishers_lock: threading.Lock = threading.Lock()

        # open socket for message-passing between clients
        self._msg_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        self._msg_port = get_available_port(host=self._host, start=self._port+1)
        self._msg_socket.bind((self._host, self._msg_port))

        self._threads: List[threading.Thread] = []

        # listen for incoming connections in separate thread
        self.listen_thread: threading.Thread = threading.Thread(target=self._listen)
        self.listen_thread.name = f"{self._name.replace('/','_')}_listen"
        self._threads.append(self.listen_thread)

        # run our spin function as a separate thread
        self.spin_thread: threading.Thread = threading.Thread(target=self._spin)
        self.spin_thread.name = f"{self._name.replace('/','_')}_spin"
        self._threads.append(self.spin_thread)

        self._rpc_server: grpc.Server
        self._executor: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(
            max_workers=10)
        self._configure_rpc_servicer()

        self._registered: bool = False
        self._ready: bool = False

        if autostart:
            self.log("DEBUG", f"{self._name} auto-starting")
            self.start()

    def start(self) -> None:

        # Idempotence
        if self._ready:
            return

        if (not self._registered) and (not self._register()):
            self.log("ERR", f"Failed to register node with tbx server.")
            raise Exception(f"Could not register node <'{self}'> with tbx-server.")

        # non-blocking
        self._rpc_server.start()

        for thread in self._threads:
            thread.start()
        
        atexit.register(self.shutdown)
        self._ready = True

    def shutdown(self, requested_by_server: bool = False) -> None:

        # Idempotence
        if self._shutdown:
            return

        self.log("INFO", f"Shutting down {self._name}. requested_by_server={requested_by_server}.")

        if requested_by_server:
            # If the server requests that we shut down, we assume that we don't
            # need to de-register with it.
            self._registered = False

        # Signal to threads that they should stop what they're doing
        self._shutdown = True

        # Make sure all connections, pubs, and subs get the signal to shutdown.
        for connection in self.connections.values():
            connection.trigger_shutdown()
        for publisher in self.publishers:
            publisher.trigger_shutdown()
        for subscriber in self.subscribers:
            subscriber.trigger_shutdown()

        # Wait for any still-living threads to finish up.
        for thread in self._threads:
            if not thread.is_alive():
                continue
            thread.join()

    def is_shutdown(self) -> bool:
        return self._shutdown or self._shutdown_event.is_set()

    def _configure_rpc_servicer(self) -> None:
        """
        Create the RPC server that we'll use to field RPCs from other clients.
        """

        self._rpc_server = grpc.server(thread_pool=self._executor)
        add_ClientServicer_to_server(
            servicer=ClientRPCServicer(
                subscribers=self._subscribers, 
                shutdown_callback=self.shutdown),
            server=self._rpc_server,
        )

        self._rpc_server.add_insecure_port(f'[::]:{self._port}')

    def _register(self) -> bool:
        """
        Attempt to register this Node with the TBX server.
        """
        
        if self._registered:
            # Don't re-register.
            return True

        # Register ourselves with the tbx-server
        result: bool = register_client_rpc(
            name=self._name, 
            host=self._host,
            port=self._port,
            data_port=self._msg_port)
        if not result:
            return False
        
        self._registered = True
        atexit.register(self._deregister)

        return True

    def _deregister(self) -> None:

        if not self._registered:
            # Don't attempt to de-register if we're notregistered, 
            # there's a chance some other shutdown hook got here first.
            return
        
        result: bool = deregister_client_rpc(name=self._name)
        if not result:
            self.log("ERR", f"Failed to de-register node <'{self._name}'>")
        self._registered = False

    # threading.Thread
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
        while not self.is_shutdown():
            try:
                conn, addr = self._msg_socket.accept()
                self.log("DEBUG", f"<{self._name}> accepted conn request from {conn.getpeername()}")
                with self._conn_lock:
                    self._connections[conn] = Connection(
                        name="",
                        sock=conn,
                        host=addr[0],
                        port=addr[1])
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

        # # TODO: I've somehow turned this whole block into dead code??? Figure that out.
        # for conn in ready_to_read:
        #     message = self._connections[conn].read(conn=conn)
        #     self._handle_message(conn=conn, message=message)

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

    # threading.Thread
    def _spin(self) -> None:
        """
        Message-handling loop.
        """
        
        # service ephemeral connections
        while not self.is_shutdown():
            
            # TODO: need this to avoid all sorts of weird messaging order issues,
            #       should probably figure out why
            time.sleep(0.01)
            
            self._spin_once()

    def _configure_publisher(
        self, 
        topic_name: str, 
        message_type: str
    ) -> Publisher:

        # create a publisher, 
        # REMEMBER: Publishers don't connect().
        publisher: Publisher = Publisher(
            topic_name=topic_name,
            message_type=message_type,
            host=self._host,
            port=get_available_port(host=self._host, start=self._msg_port),
            logger=self._logger,
            shutdown_event=self.shutdown_event
        )

        return publisher

    def _configure_subscriber(
        self, 
        topic_name: str, 
        message_type: Message, 
        publisher_info: Tuple[str,str,int] | None,
        callback: Callable | None = None,
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
            Publisher | None : If the topic was advertised properly, returns the Publisher, \
                otherwise returns None
        """

        pub: Publisher = self._configure_publisher(
            topic_name=topic_name,
            message_type=message_type)

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
        callback_fn: Callable | None = None
    ) -> bool:

        # Create subscriber FIRST to avoid race conditions with tbx-server in
        # the case that there isn't a publisher when we send the request, but 
        # there IS a publisher by the time we process the response.  
        self.log("DEBUG", f"Creating subscriber for {topic_name}.")
        subscriber: Subscriber = self._configure_subscriber(
            topic_name=topic_name,
            message_type=message_type,
            publisher_info=None,
            callback=callback_fn)

        # Request information about publishers of a specific topic.
        self.log("DEBUG", f"Requesting topic info for {topic_name} from server.")
        try:
            publishers: list[tuple[str,str,int]] = subscribe_topic_rpc(
                subscriber_id=self._name,
                topic_name=topic_name,
                message_type=message_type.DESCRIPTOR.full_name)
        except grpc.RpcError as rpc_error:
            self.log("WARN", f"Failed to get publisher info from tbx-server: {rpc_error}")
            return False
        
        if publishers:
            self.log("DEBUG", f"At least one publisher for topic <{topic_name}>: {[pub[0] for pub in publishers]}")

            # The first publisher gets assigned to the subscriber we already created.
            self.log("DEBUG", f"Connecting to publisher {publishers[0]} for topic {topic_name}")
            result: bool = subscriber.add_publisher(publishers[0])
            if not result:
                self.log("ERR", f"Failed to connect to publisher {publishers[0]}")
                return False

            if len(publishers) > 1:
                # TODO: to handle the case where multiple publishers exist for the same topic,
                # I'll likely need to change the Subscriber class to HOLD a Connection, rather than BE a Connection
                self.log("WARN", f"Multiple publishers for topic <'{topic_name}'>. This isn't handled gracefully yet.")
                for publisher in publishers[1:]:
                    self.log("DEBUG", f"Subscribing to <{topic_name}> from publisher <{publisher[0]}>")
                    self._configure_subscriber(
                        topic_name=topic_name,
                        message_type=message_type,
                        publisher_info=publisher,
                        callback=callback_fn)
        else:
            self.log("DEBUG", f"No publishers declared for topic <{topic_name}>")

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

    @property
    def ready(self) -> bool:
        return self._ready
    
    @property
    def shutdown_event(self) -> threading.Event:
        return self._shutdown_event
