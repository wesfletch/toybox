#!/usr/bin/env python3

from abc import ABC
import atexit
import errno
from queue import Queue, Empty
import socket
import sys
import threading
from typing import Dict, List, Union, Tuple

import grpc
import concurrent.futures as futures

# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')

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
        others: List[str],
    ) -> None:
        
        self._subscriptions = subscriptions
        self._others = others

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


class Node():

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50505,
        # sock: Union[socket.socket,None] = None,
    ) -> None:

        self._shutdown: bool = False

        self._host: str = host
        self._port: int = port
        # self._socket: Union[socket.socket,None] = sock
        # if self._msg_socket is None:
        self._msg_socket = socket.socket(family=socket.AF_INET, 
                                         type=socket.SOCK_STREAM)
        self._msg_socket.bind((self._host, get_available_port(host=self._host, start=self._port+1)))

        self._executor: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(
            max_workers=10
        )

        self._inbound: Dict[socket.socket, Queue[str]] = {}
        self._outbound: Dict[socket.socket, Queue[str]] = {}

        self._subscriptions: Dict[str, Topic] = {}
        self._others: List[str] = []

        # listen for incoming connections in separate thread
        self.listen_thread: threading.Thread = threading.Thread(target=self.listen)
        self.listen_thread.start()

        self.configure_rpc_servicer()

        atexit.register(self.cleanup, self)

    def configure_rpc_servicer(self) -> None:

        self._server = grpc.server(
            thread_pool=self._executor,
        )
        add_ClientServicer_to_server(
            servicer=ClientRPCServicer(
                subscriptions=self._subscriptions, 
                others=self._others),
            server=self._server,
        )

        self._server.add_insecure_port(f'[::]:{self._port}')

        # non-blocking
        self._server.start()

    def listen(self) -> None:

        # enable socket to accept connections
        self._msg_socket.listen()
        # make socket non-blocking
        self._msg_socket.settimeout(0) 

        # listen for new connections to add to list
        while not self._shutdown:
            try:
                conn, addr = self._msg_socket.accept()
                self._connections[conn] = Queue()
            except BlockingIOError:
                pass

    def handshake(self) -> None:
        pass

    def spin(
        self
    ) -> None:
        pass

    def cleanup(self) -> None:

        self._shutdown = True

        self._msg_socket.shutdown(socket.SHUT_RDWR)
        self._msg_socket.close()


class MessageHandshake():
    """
    Manages the lifetime of a handshake between a publisher and a subscriber.
    """
    def __init__(
        self, 
        topic_name: str, 
        message_type: str
    ) -> None:
        pass

    def next(self, input: str) -> None:
        
        pass

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

    # sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # if not port_in_use(port=port, host=host):
    #     try:
    #         sock.bind(address)
    #     except socket.error as e:
    #         # define custom exceptions/actually handle socket errors?
    #         raise Exception(e)
        
    node: Node = Node(host=host,
                      port=port)
    
    # if not standalone:
    # register ourselves with the master
    if not register_client_rpc(name=name, addr=address):
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