#!/usr/bin/env python3

from abc import ABC
import atexit
from dataclasses import dataclass, field
import errno
from queue import Queue, Empty
import select
import socket
import struct
import sys
import threading
import time
from typing import Dict, List, Union, Tuple, Callable
import uuid

import grpc
from google.protobuf.message import Message, DecodeError
import concurrent.futures as futures

# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')

from toybox_core.src.ClientServer import (
    ClientRPCServicer
)
from toybox_core.src.Connection import (
    Connection,
    Subscriber,
    Publisher,
    # Transaction,
    get_available_port,
)

import toybox_msgs.core.Register_pb2 as Register_pb2
from toybox_core.src.RegisterServer import (
    register_client_rpc,
    deregister_client_rpc,
    get_client_info_rpc,
)
from toybox_core.src.TopicServer import (
    advertise_topic_rpc,
    subscribe_topic_rpc,
    Topic,
)

import toybox_msgs.core.Client_pb2 as Client_pb2
from toybox_msgs.core.Client_pb2_grpc import (
    ClientServicer,
    add_ClientServicer_to_server,
)
import toybox_msgs.core.Topic_pb2 as Topic_pb2

from toybox_core.src.Logging import LOG

class Node():

    def __init__(
        self,
        name: str,
        host: str = "localhost",
        port: int = 50505,
        # sock: Union[socket.socket,None] = None,
    ) -> None:

        self._name = name
        self._host: str = host
        self._port: int = port

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
        self.listen_thread: threading.Thread = threading.Thread(target=self.listen)
        self.listen_thread.start()

        # run our spin function as a separate thread
        self.spin_thread: threading.Thread = threading.Thread(target=self.spin)
        self.spin_thread.start()

        self._threads: List[threading.Thread] = []

        self._executor: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(
            max_workers=10
        )
        self.configure_rpc_servicer()

        atexit.register(self.cleanup)

    def cleanup(self) -> None:
        self._shutdown = True
        # deregister_client_rpc(self._name)

    def configure_rpc_servicer(self) -> None:

        self._rpc_server = grpc.server(
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

    def listen(self) -> None:
        """
        THREAD
        """

        # enable socket to accept connections
        self._msg_socket.listen()
        # make socket non-blocking
        self._msg_socket.settimeout(0)

        # listen for new connections to add to list
        while not self._shutdown:
            try:
                conn, addr = self._msg_socket.accept()
                LOG("DEBUG", f"<{self._name}> accepted conn request from {conn.getpeername()}")
                with self._conn_lock:                
                    self._connections[conn] = Connection(
                        name="",
                        sock=conn,
                        host=addr[0],
                        port=addr[1],
                    )
            except BlockingIOError:
                continue

        self._msg_socket.shutdown(socket.SHUT_RDWR)
        self._msg_socket.close()

    def handshake(self) -> None:
        pass

    def spin(
        self
    ) -> None:
        
        ready_to_read: List[socket.socket] = []
        ready_to_write: List[socket.socket] = []
        
        # service ephemeral connections, publishers, and subscribers in series
        # a better(?) way to handle this would be spinning pubs/subs into their own self-contained threads 
        while not self._shutdown:
            
            # service ephemeral connections
            if not self._conn_lock.acquire(blocking=False):
                continue

            # get available [in/out]bound sockets
            connections: List[socket.socket] = self._connections.keys() 
            ready_to_read, ready_to_write, _ = select.select(connections, 
                                                             connections, 
                                                             [], 0)
            self._conn_lock.release()

            for conn in ready_to_read:    
                self.read(conn=conn)

            for conn in ready_to_write:
                connection: Union[Connection,None] = self.connections.get(conn, None)
                if connection is None:
                    # connection might have been deleted by another thread
                    continue
                elif connection.initialized == False:
                    # we can't trust un-initialized connections to behave
                    continue

                try:
                    message: bytes = self._connections[conn].outbound.get(block=False)
                except Empty:
                    continue

                LOG("DEBUG", f"<{self._name}> sent message to {self._connections[conn].name}: {message}")
                self._connections[conn].sock.sendall(message)

            # service publishers
            publishers: List[socket.socket] = [x.sock for x in self.publishers]
            _, ready_to_write, _ = select.select([], publishers,
                                                 [], 0)
            for publisher in ready_to_write:
                pass

            # service subscribers
            subscribers: List[socket.socket] = [x.sock for x in self.subscribers]
            ready_to_read, _, _ = select.select(subscribers, 
                                                [], [], 0)
            for subscriber in ready_to_read:
                pass

            # TODO: need this to avoid all sorts of weird messaging order issues,
            #       should probably figure out why
            time.sleep(0.01)

    def read(
        self, 
        conn: socket.socket,
    ) -> None:
        
        try:
            len_bytes: bytes = conn.recv(2)
        except socket.error as e:
            if e.errno == 107: # transport endpoint not connected
                with self._conn_lock:
                    LOG("DEBUG", f"transport client {self._connections[conn].sock} disconnected.")
                    del self._connections[conn]
            return None

        # unpack (L)ength -> first two bytes
        data_len: int = struct.unpack("H", len_bytes)[0]
        # receive (T)ype and (V)alue
        received: bytes = conn.recv(data_len)

        self.handle_message(conn, received)

    def handle_message(
        self, 
        conn: socket.socket, 
        message: bytes,
    ) -> None:

        msg_split = message.splitlines(keepends=True)
        message_type: str = msg_split[0].decode('utf-8')
        message_type = message_type.rstrip('\n')
        message_data: bytes = b'\n' + b''.join(msg_split[1:])

        # dispatch subscribed messages to their appropriate callbacks
        topic: Union[Topic,None] = self._connections.get(conn, None).topic
        if topic is not None:
            # ensure that this is the correct
            if message_type != topic.message_type:
                LOG("ERR", f"message type <{message_type}> doesn't match topic message type <{topic.message_type}>")
                return
            if topic.callback is None:
                LOG("INFO", "NO CALLBACK DECLARED")
                return

        LOG("DEBUG",f'<{self._name}> received: \n\tmessage_type=<{message_type}>\n\tmessage={message_data!r}')

        # TODO: these should really be broken out into callbacks
        if message_type == "core.ClientInfo":
            # this is another client introducing themselves
            client_info: Register_pb2.ClientInfo = Register_pb2.ClientInfo()
            try:
                client_info.ParseFromString(message_data)
            except DecodeError as e:
                LOG("ERR", f"We just got garbage: {e}")
                return
            
            if not self._connections[conn].initialized:
                LOG("DEBUG", f"{self._name} initializing connection with {client_info.client_id}")
                self._connections[conn].name = client_info.client_id
                self._connections[conn].initialized = True
            else:
                LOG("DEBUG", "already initialized")
                return
            
        elif message_type == "core.Confirmation":
            
            confirmation: Topic_pb2.Confirmation = Topic_pb2.Confirmation()
            try:
                confirmation.ParseFromString(message_data)
            except DecodeError as e:
                LOG("ERR", f"We just got garbage: {e}")
                return
            
            LOG("DEBUG", f"{self._name}: {confirmation}")

        else:
            LOG("DEBUG", f"got unhandled message type: <{message_type}>")
            # messages that aren't explicitly handled just go into the inbound queues
            self._connections[conn].inbound.put(message.decode('utf-8'))

    def configure_publisher(self, topic_name: str, message_type: str) -> Publisher:

        # create a publisher connection
        publisher: Publisher = Publisher(
            topic_name=topic_name,
            message_type=message_type,
            host=self._host,
            port=get_available_port(host=self._host, start=self._msg_port),
        )

        self.publishers.append(publisher)
        return publisher

    def configure_subscriber(
        self, 
        topic_name: str, 
        message_type: str, 
        publisher_info: Tuple[str,str,int],
        callback: Union[Callable, None] = None,
    ) -> Subscriber:

        subscriber: Subscriber = Subscriber(
            topic_name=topic_name,
            message_type=message_type,
            host=self._host,
            port=get_available_port(host=self._host, start=self._msg_port),
            publisher_info=publisher_info,
            callback=callback
        )

        self.subscribers.append(subscriber)
        return subscriber

    def subscribe(
        self,
        topic_name: str,
        message_type: str,
        callback_fn: Callable
    ) -> bool:
    
        # request information about publishers of a specific topic
        LOG("DEBUG", f"{self._name} requesting topic information")
        try:
            publishers: List[Tuple[str, int]] = subscribe_topic_rpc(
                topic_name=topic_name,
                message_type=message_type)
        except grpc.RpcError as rpc_error:
            LOG("ERR", f"that didn't work: {rpc_error}")
            return False
        
        # TODO: actually do something even if a publisher isn't declared
        if len(publishers) == 0:
            LOG("DEBUG", f"no publishers declared for topic <{topic_name}>")
            self.configure_subscriber(
                topic_name=topic_name,
                message_type=message_type,
                publisher_info=None,
                callback=callback_fn,
            )
        else:
            for publisher in publishers:
                self.configure_subscriber(
                    topic_name=topic_name,
                    message_type=message_type,
                    publisher_info=publisher,
                    callback=callback_fn,
                )

        return True
        
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