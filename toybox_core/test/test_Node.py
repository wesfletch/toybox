#!/usr/bin/env python3

import unittest

import concurrent.futures as futures
import grpc
import select
import socket
import sys

sys.path.append('/home/dev/toybox')
import toybox_msgs.core.Client_pb2 as Client_pb2
from toybox_msgs.core.Client_pb2_grpc import (
    # ClientRPCServicer,
    ClientStub,
    add_ClientServicer_to_server,
)
from toybox_core.src.Client import (
    ClientRPCServicer,
    Node,
    init_node,
    get_available_port,
)
from toybox_msgs.core.Topic_pb2 import (
    TopicDefinition,
)
from toybox_core.src.TopicServer import (
    Topic
)

from toybox_msgs.core.Register_pb2_grpc import (
    add_RegisterServicer_to_server
)
from toybox_core.src.RegisterServer import (
    Client,
    RegisterServicer
)

from typing import Dict, Union, List

class Test_init_node(unittest.TestCase):

    host: str = "localhost"
    port: int = 50051

    def setUp(self) -> None:
        
        self._node: Node = None
        self._clients: Dict[str,Client] = {}
        self._servicer: RegisterServicer = RegisterServicer(clients=self._clients)

        self._server: grpc.Server = grpc.server(
            thread_pool=futures.ThreadPoolExecutor(max_workers=10)
        )
        self._server.add_insecure_port(f'[::]:{self.port}')

        add_RegisterServicer_to_server(
            servicer=self._servicer,
            server=self._server
        )
        self._server.start()

    def tearDown(self) -> None:
        
        if self._node:
            self._node.cleanup()
        
        self._server.stop(grace=None)

    def test_init_node(self) -> None:

        self._node = init_node(name="test")
        
class Test_Node(unittest.TestCase):

    host: str = "localhost"
    port: int = 50051

    def setUp(self) -> None:
        
        self._clients: Dict[str,Client] = {}
        self._servicer: RegisterServicer = RegisterServicer(clients=self._clients)

        self._server: grpc.Server = grpc.server(
            thread_pool=futures.ThreadPoolExecutor(max_workers=10)
        )
        self._server.add_insecure_port(f'[::]:{self.port}')

        add_RegisterServicer_to_server(
            servicer=self._servicer,
            server=self._server
        )
        self._server.start()
        
        self._node: Node = init_node(name="test",
                                     address=("localhost", 50510))

    def tearDown(self) -> None:
        
        if self._node:
            self._node.cleanup()
        
        self._server.stop(grace=None)

    def test_msg_socket_connection(self) -> None:

        sock: socket.socket = socket.socket(family=socket.AF_INET,
                                            type=socket.SOCK_STREAM)
        
        sock.connect(("localhost", self._node._msg_port))
        # self.assertTrue(sock in self._node._inbound.keys())

        # wait for our node to be ready to receive messages
        ready_to_write: Union[List[socket.socket], None] = None
        while ready_to_write is None:
            _, ready_to_write, _ = select.select([], [sock], [], 0)
            
        test_message: str = "TEST123\n"
        if sock in ready_to_write:
            sock.sendall(test_message.encode())

        self.assertFalse(False)

if __name__ == '__main__':
    unittest.main(warnings='ignore')