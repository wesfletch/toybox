#!/usr/bin/env python3

import unittest

import concurrent.futures as futures
import grpc
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
        
        self._clients: Dict[str,Client] = {}
        self._servicer: RegisterServicer = RegisterServicer(clients=self._clients)

        self._server = grpc.server(
            thread_pool=futures.ThreadPoolExecutor(max_workers=10)
        )
        self._server.add_insecure_port(f'[::]:{self.port}')

        add_RegisterServicer_to_server(
            servicer=self._servicer,
            server=self._server
        )
        self._server.start()

    def tearDown(self) -> None:
        self._server.stop(grace=None)

    def test_init_node(self) -> None:

        node = init_node(name="test")

        node.cleanup()
        
        assert True

# class Test_Node(unittest.TestCase):

#     host: str = "localhost"
#     port: int = 50505

#     def setUp(self) -> None:
        
#         self._node = init_node("test")        

#     def test_msg_socket_connection(self) -> None:

#         self.assertFalse(True)
    
if __name__ == '__main__':
    unittest.main()