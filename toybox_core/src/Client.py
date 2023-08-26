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
from typing import Dict, List, Union, Tuple, Callable

import grpc
from google.protobuf.message import Message, DecodeError
import concurrent.futures as futures

# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')

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
from toybox_msgs.core.Topic_pb2 import (
    TopicDefinition,
)

class ClientRPCServicer(ClientServicer):

    def __init__(
        self, 
        subscriptions: Dict[str, Topic],
        # shutdown_flag: bool,
        # others: List[str],
    ) -> None:
        
        self._subscriptions = subscriptions
        # self._shutdown_flag = shutdown_flag
        # self._others = others

    def InformOfPublisher(
        self, 
        request: TopicDefinition, 
        context
    ) -> Client_pb2.InformConfirmation:
        
        publisher_uuid: str = request.uuid
        topic: str = request.topic_name
        message_type: str = request.message_type

        subscription = self._subscriptions.get(topic, None)

        # first, make sure we actually care about this message
        if subscription is None:
            return Client_pb2.InformConfirmation(
                return_code=1,
                status="I don't think I asked for this."
            )
        # and message type is correct
        if subscription.message_type != message_type:
            return Client_pb2.InformConfirmation(
                return_code=2,
                status=f"Unexpected message type {message_type}, expected {subscription.message_type}"
            )

        subscription.publishers.append(publisher_uuid)
        return Client_pb2.InformConfirmation(
            return_code=0,
        )
    
    # def InformOfShutdown(self, request, context):
    #     pass

@dataclass
class Connection():
    name: str
    sock: socket.socket
    host: str
    port: int

    initialized: bool = False

    inbound: "Queue[str]" = field(default_factory=Queue)
    outbound: "Queue[str]" = field(default_factory=Queue)

    in_lock: threading.Lock = threading.Lock()

    def wait_for_inbound(self, blocking: bool = True) -> bool:
        """Test synchronization"""
        if blocking:
            while self.inbound.qsize() == 0:
                continue
            return True
        else:
            return self.inbound.qsize() != 0
        
    def wait_for_outbound(self, blocking: bool = True) -> bool:
        "Test synchronization"
        if blocking:
            while self.outbound.qsize() != 0:
                continue
            return True
        else:
            return self.inbound.qsize() == 0

        
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
                # unpack (L)ength -> first two bytes
                data_len: int = struct.unpack("H", conn.recv(2))[0]
                # receive (T)ype and (V)alue
                received: bytes = conn.recv(data_len)

                # self._connections[conn].inbound.put(message)
                self.handle_message(conn, received)

            for conn in ready_to_write:
                # we can't trust un-initialized connections to behave
                if not self._connections[conn].initialized:
                    continue

                try:
                    message: str = self._connections[conn].outbound.get(block=False)
                except Empty:
                    continue
                
                self._connections[conn].sock.sendall(message)

            # # handle subscriptions
            # for sub in subscriptions:
            #   if sub.publishers is in connections and publisher.inbound is not empty
            #       pass messages to callbacks

            # # handle publications
            # for pub in publications:
            #   pub.subscribers is in connections and subscriber.outbound is not empty
            #       send message to subscriber

    def handle_message(self, conn: socket.socket, message: Union[bytes, None]) -> None:

        # potentially unnecessary mutex
        self._connections[conn].in_lock.acquire()

        msg_split = message.splitlines(keepends=True)
        message_type: bytes = msg_split[0].decode('utf-8').strip()
        message_data: bytes = b'\n' + b''.join(msg_split[1:])

        # print(f'\n<{self._name}> received: \n\tmessage_type={message_type}\n\tmessage={message_data}')

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
        else:
            # messages that aren't explicitly handled just go into the inbound queues
            self._connections[conn].inbound.put(message)

        self._connections[conn].in_lock.release()

    def send_message(
        self, 
        conn: socket, 
        message: Message
    ) -> None:
        """
        Send message to a configured connection. 
        Messages are in Length-Type-Value (LTV) format.

        Args:
            conn (socket): connection to send message to
            message (Message): message (pb2) to send to `conn`
        """

        # pack (T)ype and (V)alue
        message_type: bytes = message.DESCRIPTOR.full_name.encode()
        message_bytes: bytes = message.SerializeToString()

        # prepend messages with (L)ength
        data_len = struct.pack("H", len(message_type) + len(message_bytes))
        
        # pack bytes
        packed_message: bytearray = b""
        packed_message += data_len
        packed_message += message_type
        packed_message += message_bytes

        # place into outbound queue to be handled by spin()
        self._connections[conn].outbound.put(packed_message)

    def introduce(
        self, 
        other_client: str, 
        conn: socket.socket
    ) -> None:

        # generate a ClientInfo message for this client
        intro_msg: Register_pb2.ClientInfo = Register_pb2.ClientInfo()
        intro_msg.client_id = self._name
        metadata: Register_pb2.ClientMetadata = Register_pb2.ClientMetadata()
        metadata.addr = self._msg_socket.getsockname()[0]
        metadata.port = self._msg_socket.getsockname()[1]
        intro_msg.meta.CopyFrom(metadata)

        if conn not in self._connections.keys():
            # attempt to connect to other client
            sock: socket.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
            conn_host: str = conn.getsockname()[0]
            conn_port: int = conn.getsockname()[1]
            sock.connect((conn_host, conn_port))

            # self._msg_socket.connect((conn_host, conn_port))
            self._connections[sock] = Connection(
                name=other_client,
                sock=sock,
                host=sock.getpeername()[0],
                port=sock.getpeername()[1],
                initialized=True
            )
            
        self.send_message(conn=sock, message=intro_msg)

    def subscribe(
        self,
        topic_name: str,
        message_type: str,
        callback_fn: Callable
    ) -> bool:
    
        try:
            publishers: Union[List[str],None] = subscribe_topic_rpc(
                client_name=self._name,
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

        if topic.publishers is not None:
            for publisher in topic.publishers:
                # we don't need to request info if we already have it
                if self.get_connection(publisher) is not None:
                    continue

                publisher_info: Register_pb2.ClientInfo = get_client_info_rpc(publisher)
                publisher_conn: Connection = Connection(
                    name=publisher,
                    sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
                    host=publisher_info.meta.addr,
                    port=publisher_info.meta.data_port,
                    initialized=False
                )
                self._connections[publisher_conn.sock] = publisher_conn

        self._subscriptions[topic.name] = topic

        return True
    
    def advertiseTopic(
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
    
    def get_connection(self, name: str) -> Union[Connection, None]:
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


def port_in_use(port: int, host: str = 'localhost') -> bool:

    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.bind((host, port))
    except socket.error as e:
        if e.errno == errno.EADDRINUSE:
            return True
        # else:
        # should this handle other exceptions?
    sock.close()
    return False

def get_available_port(
    host: str = "localhost",
    start: int = 50505
) -> int:

    port: int = start
    while port_in_use(port=port, host=host):
        port += 1
    return port

def is_shutdown() -> bool:
    return False

def deinit_node(
    name: str,
) -> None:
    
    deregister_client_rpc(name=name)

def init_node(
    name: str,
    address: Union[Tuple[str,int], None] = None,
) -> Node:
    
    atexit.register(deinit_node, name)

    if not address:
        host: str = "localhost"
        port: int = get_available_port(host="localhost")
        address = (host, port)
    else:
        host, port = address

    node: Node = Node(name=name, 
                      host=host, 
                      port=port)

    # register ourselves with the master
    if not register_client_rpc(name=node._name, 
                               host=node._host,
                               port=node._port,
                               data_port=node._msg_port):
        print("we fucked up, I guess")

    return node

def advertise_topic(
    client_name: str,
    topic_name: str,
    message_type: str,
) -> bool:

    return advertise_topic_rpc(
        client_name=client_name,
        topic_name=topic_name,
        message_type=message_type,
    )

def subscribe_topic(
    client_name: str,
    topic_name: str,
    message_type: str,
) -> bool:

    publishers: List[str] = subscribe_topic_rpc(
        client_name=client_name,
        topic_name=topic_name,
        message_type=message_type,
    )
    
    for publisher in publishers:
        pass

def main():

    node = init_node(name="quetzal")

    # result = advertise_topic(
    #     client_name="quetzal",
    #     topic_name="fucker",
    #     message_type="also_fucker"
    # )
    # print(result)
    
    # result = subscribe_topic(
    #     client_name="quetzal",
    #     topic_name="buttest",
    #     message_type="butter"
    # )
    # print(result)

    # get_client_info_rpc(client_name="quetzal")

    # while True:
    #     pass

if __name__ == "__main__":
    main()