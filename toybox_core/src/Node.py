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
    Transaction,
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

        # queue of messages for inbound and outbound connections
        self._connections: Dict[socket.socket, Connection] = {}
        # inbound topics
        self._subscriptions: Dict[str, Topic] = {}
        # outbound topics
        self._publications: Dict[str, Topic] = {}

        # open socket for message-passing between clients
        self._msg_socket = socket.socket(family=socket.AF_INET, 
                                         type=socket.SOCK_STREAM)
        self._msg_port = get_available_port(host=self._host, start=self._port+1)
        self._msg_socket.bind((self._host, self._msg_port))

        # thread management
        self._shutdown: bool = False
        self._msg_lock: threading.Lock = threading.Lock()

        # listen for incoming connections in separate thread
        self.listen_thread: threading.Thread = threading.Thread(target=self.listen)
        self.listen_thread.start()

        # run our spin function as a separate thread
        self.spin_thread: threading.Thread = threading.Thread(target=self.spin)
        self.spin_thread.start()

        self._executor: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(
            max_workers=10
        )
        self.configure_rpc_servicer()

        atexit.register(self.cleanup)

    def configure_rpc_servicer(self) -> None:

        self._server = grpc.server(
            thread_pool=self._executor,
        )
        add_ClientServicer_to_server(
            servicer=ClientRPCServicer(
                subscriptions=self._subscriptions, 
                # others=self._others,
                ),
            server=self._server,
        )

        self._server.add_insecure_port(f'[::]:{self._port}')

        # non-blocking
        self._server.start()

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
                print(f"{self._name} accepted conn request from {conn}")
                with self._msg_lock:                
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
        
        while not self._shutdown:

            if not self._msg_lock.acquire(blocking=False):
                continue

            # get available [in/out]bound sockets
            ready_to_read, ready_to_write, _ = select.select(self._connections.keys(), 
                                                             self._connections.keys(), 
                                                             [], 0)
            self._msg_lock.release()

            for conn in ready_to_read:    
                self.read(conn=conn)

            for conn in ready_to_write:
                # we can't trust un-initialized connections to behave
                if not self._connections[conn].initialized:
                    continue

                try:
                    message: str = self._connections[conn].outbound.get(block=False)
                except Empty:
                    continue
                
                # print(f"{self._name} sent message to {self._connections[conn].name}")
                self._connections[conn].sock.sendall(message)

            # # handle subscriptions
            # for sub in self._subscriptions.values():
            #   if sub.publishers is in connections and publisher.inbound is not empty
            #       pass messages to callbacks

            # # handle publications
            # for pub in publications:
            #   pub.subscribers is in connections and subscriber.outbound is not empty
            #       send message to subscriber

            # TODO: need this to avoid all sorts of weird messaging order issues,
            #       should probably figure out why
            time.sleep(0.01)

    def read(
        self, 
        conn: socket.socket,
    ) -> None:
        
        # unpack (L)ength -> first two bytes
        data_len: int = struct.unpack("H", conn.recv(2))[0]
        # receive (T)ype and (V)alue
        received: bytes = conn.recv(data_len)

        # self._connections[conn].inbound.put(message)
        self.handle_message(conn, received)

    def handle_message(
        self, 
        conn: socket.socket, 
        message: Union[bytes, None]
    ) -> None:

        # potentially unnecessary mutex
        self._connections[conn].in_lock.acquire()

        msg_split = message.splitlines(keepends=True)
        message_type: str = msg_split[0].decode('utf-8')
        message_type = message_type.rstrip('\n')
        message_data: bytes = b'\n' + b''.join(msg_split[1:])

        print(f'\n<{self._name}> received: \n\tmessage_type=<{message_type}>\n\tmessage={message_data}')

        # if this is part of a currently running transaction, pass it to the transaction to handle

        print(f"{self._name}: message_type = <{message_type}>")
        # TODO: these should really be broken out into callbacks
        if message_type == "core.ClientInfo":
            # this is another client introducing themselves
            
            client_info: Register_pb2.ClientInfo = Register_pb2.ClientInfo()
            try:
                client_info.ParseFromString(message_data)
            except DecodeError as e:
                print(f"We just got garbage: {e}")
                return
            
            if not self._connections[conn].initialized:
                self._connections[conn].name = client_info.client_id
                self._connections[conn].initialized = True
            else:
                print('already initialized')
                return
        
        elif message_type == "core.SubscriptionRequest":

            sub_request: Topic_pb2.SubscriptionRequest = Topic_pb2.SubscriptionRequest()
            try:
                sub_request.ParseFromString(message_data)
            except DecodeError as e:
                print(f"We just got garbage: {e}")
                return

            sub_topic_name: str = sub_request.topic_def.topic_name
            sub_message_type: str = sub_request.topic_def.message_type

            response: Topic_pb2.SubscriptionResponse = Topic_pb2.SubscriptionResponse()
            response.conf.uuid = sub_request.topic_def.uuid
            response.conf.return_code = 0
            response.topic_def.CopyFrom(sub_request.topic_def)

            if sub_topic_name not in self._publications:
                response.conf.return_code = 1
                response.conf.status = f"{self._name} not publishing topic {sub_topic_name}"            
            elif self._publications[sub_topic_name].message_type != sub_message_type:
                response.conf.return_code = 2
                response.conf.status = f"{sub_message_type} doesn't match advertiser declared message type \
                    {self._publications[sub_topic_name].message_type}"

            # create a publisher connection
            topic_connection: Connection = Connection(
                name=f"{sub_topic_name}_publisher_{str(uuid.uuid1())}",
                sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
                host=self._host,
                port=get_available_port(host=self._host, start=self._msg_port),
                topic=self._publications[sub_topic_name],
            )
            self._connections[topic_connection.sock] = topic_connection
            # and inform our subscriber of what port to connect to
            response.topic_port = topic_connection.port

            self.send_message(
                conn=conn, 
                message=response, 
                enqueue=True
            )

        elif message_type == "core.SubscriptionResponse":
            print("fuck yeah")
            
        elif message_type == "core.Confirmation":
            
            confirmation: Topic_pb2.Confirmation = Topic_pb2.Confirmation()
            try:
                confirmation.ParseFromString(message_data)
            except DecodeError as e:
                print(f"We just got garbage: {e}")
                return
            
            print(f"{self._name}: {confirmation}")

        else:
            # messages that aren't explicitly handled just go into the inbound queues
            self._connections[conn].inbound.put(message)

        self._connections[conn].in_lock.release()

    def send_message(
        self, 
        conn: socket.socket, 
        message: Message,
        enqueue: bool = True
    ) -> None:
        """
        Send message to a configured connection. 
        Messages are in Length-Type-Value (LTV) format.

        Args:
            conn (socket): connection to send message to
            message (Message): message (pb2) to send to `conn`
        """

        # pack (T)ype and (V)alue
        print(f"sending <{message.DESCRIPTOR.full_name}>")
        # message_type: bytes = "".join([message.DESCRIPTOR.full_name, "\n"]).encode('utf-8')
        message_type: bytes = message.DESCRIPTOR.full_name.encode('utf-8')
        print(f"sending message type <{message_type}>")
        message_bytes: bytes = message.SerializeToString()

        # prepend messages with (L)ength
        data_len = struct.pack("H", len(message_type) + len(message_bytes))
        
        # pack bytes
        packed_message: bytearray = b""
        packed_message += data_len
        packed_message += message_type
        packed_message += message_bytes

        print(f"{self._name} enqueued message for {self._connections[conn].name}: \
              \ntype = <{repr(message.DESCRIPTOR.full_name)}>\n{message}")
        
        if enqueue:
            # place into outbound queue to be handled by spin()...
            self._connections[conn].outbound.put(packed_message)
        else:
            # ... or just send it directly
            self._connections[conn].sock.sendall(packed_message)

    def introduce(
        self, 
        other_client: str, 
        conn: Union[socket.socket, None] = None
    ) -> None:

        # generate a ClientInfo message for this client
        intro_msg: Register_pb2.ClientInfo = Register_pb2.ClientInfo()
        intro_msg.client_id = self._name
        metadata: Register_pb2.ClientMetadata = Register_pb2.ClientMetadata()
        metadata.addr = self._msg_socket.getsockname()[0]
        metadata.port = self._msg_socket.getsockname()[1]
        intro_msg.meta.CopyFrom(metadata)

        # ensure we're actually connected to `other_client`
        if self.get_connection(other_client) is None:
            
            if conn is None:
                raise Exception(f"No connection for Client <{other_client}>, and no connection info provided. Who is this???")

            new_connection: Connection = Connection(
                name=other_client,
                sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
                host=conn.getsockname()[0],
                port=conn.getsockname()[1]
            )
            new_connection.connect()
            self._connections[new_connection.sock] = new_connection

            print(f"{self._name}: {self.get_connection(other_client)}")
        elif not self.get_connection(other_client).initialized:
            self.get_connection(other_client).connect()

        # send the introduction message
        self.send_message(conn=self.get_connection(other_client).sock, message=intro_msg)

    def subscribe(
        self,
        topic_name: str,
        message_type: str,
        callback_fn: Callable
    ) -> bool:
    
        # request information about publishers of a specific topic
        print(f"{self._name} requesting topic information")
        try:
            publishers: Union[List[str],None] = subscribe_topic_rpc(
                topic_name=topic_name,
                message_type=message_type)
        except grpc.RpcError as rpc_error:
            print(f"that didn't work: {rpc_error}")
            return False
        
        topic: Topic = Topic(
            name=topic_name,
            message_type=message_type,
            publishers=publishers if publishers is not None else [],
        )
        topic.callbacks.append(callback_fn)
        self._subscriptions[topic.name] = topic

        if topic.publishers is None:
            print(f'{self._name} exiting early')
            return True

        # get information on publishers from register server
        for publisher in topic.publishers:
            # we don't need to request info if we already have it
            if self.get_connection(publisher) is not None:
                continue

            publisher_info: Register_pb2.ClientInfo = get_client_info_rpc(publisher)
            # print(f'this is the publisher_info: {publisher_info}')
            publisher_conn: Connection = Connection(
                name=publisher,
                sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
                host=publisher_info.meta.addr,
                port=publisher_info.meta.data_port,
                initialized=False
            )
            print(f"{self._name} adding connection: {publisher_conn}")
            self._connections[publisher_conn.sock] = publisher_conn
            # print(f'this is the connection: {self._connections[publisher_conn.sock]}')

        # introduce ourself to the publisher(s)
        for publisher in topic.publishers:
            if not self.get_connection(publisher).initialized:
                self.introduce(other_client=publisher)
        
        # request a subscription from the publisher(s)
        for publisher in topic.publishers:
            self.request_subscription(
                topic=topic,
                publisher=publisher
            )
        
        return True
    
    def request_subscription(
        self,
        topic: Topic,
        publisher: str
    ) -> None:
        
        subscribe_req: Topic_pb2.SubscriptionRequest = Topic_pb2.SubscriptionRequest(
            topic_def=Topic_pb2.TopicDefinition(
                uuid=self._name,
                topic_name=topic.name,
                message_type=topic.message_type,
            )
        ) 
        self.send_message(
            conn=self.get_connection(publisher).sock,
            message=subscribe_req,
            enqueue=False,
        )
        
    def advertise_topic(
        self,
        topic_name: str,
        message_type: str
    ) -> bool:
        
        try:
            advertise_topic_rpc(
                client_name=self._name,
                topic_name=topic_name,
                message_type=message_type
            )
        except grpc.RpcError as rpc_error:
            print(f"that didn't work: {rpc_error}")
            return False

        self._publications[topic_name] = Topic(
            name=topic_name,
            message_type=message_type
        )

        return True

    def cleanup(self) -> None:
        self._shutdown = True
        # deregister_client_rpc(self._name)
        
    @property
    def connections(self) -> Dict[socket.socket,Connection]:
        with self._msg_lock:
            return self._connections
    
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
            return self.connections
        else:
            return len(self._connections) != 0
    
    def wait_for_initialized(self) -> bool:
        """Test synchronization"""
        not_initialized: List[Connection] = [x for x in self._connections.values() if not x.initialized]
        while len(not_initialized) != 0:
            not_initialized = [x.sock for x in self._connections.values() if not x.initialized]