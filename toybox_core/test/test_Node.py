#!/usr/bin/env python3

import unittest

import concurrent.futures as futures
import grpc
from queue import Queue
import select
import socket
import struct
import sys
import threading

import toybox_msgs.core.Client_pb2 as Client_pb2
from toybox_msgs.core.Client_pb2_grpc import (
    # ClientRPCServicer,
    ClientStub,
    add_ClientServicer_to_server,
)
from toybox_core.ClientServer import (
    ClientRPCServicer,
)

from toybox_core.Connection import (
    Connection,
)

from toybox_core.Node import (
    Node,
    get_available_port
)
from toybox_core.Client import (
    init_node,
)

from toybox_msgs.core.Topic_pb2_grpc import (
    add_TopicServicer_to_server
)
from toybox_msgs.core.Topic_pb2 import (
    TopicDefinition,
)
from toybox_core.TopicServer import (
    Topic,
    TopicServicer
)

import toybox_msgs.core.Register_pb2 as Register_pb2
from toybox_msgs.core.Register_pb2_grpc import (
    add_RegisterServicer_to_server
)
from toybox_core.RegisterServer import (
    Client,
    RegisterServicer,
    RegisterServer
)

from typing import Dict, Union, List

class Test_init_node(unittest.TestCase):

    host: str = "localhost"
    port: int = 50051

    def setUp(self) -> None:
        
        self._node: Union[Node,None] = None
        
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
        
        if self._node is not None:
            self._node.cleanup()
        
        stopping: threading.Event = self._server.stop(grace=None)
        stopping.wait()

    def test_init_node(self) -> None:

        self._node = init_node(name="test")

@unittest.skip('for now')
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
        
        self._node: Union[Node,None] = init_node(name="test", address=("localhost", 50510))
        
        self._sock: socket.socket = socket.socket(family=socket.AF_INET,
                                            type=socket.SOCK_STREAM)
        
    def tearDown(self) -> None:
        
        if self._node:
            self._node.cleanup()
        
        stopping: threading.Event = self._server.stop(grace=None)
        stopping.wait()

    def test_msg_socket_connection(self) -> None:

        # connect for sending
        self._sock.connect(("localhost", self._node._msg_port))

        # ensure that our socket is present in node connections
        sock_laddr = self._sock.getsockname()
        sock_raddr = self._sock.getpeername()

        self._node.wait_for_connections(blocking=True)
        connections: List[socket.socket] = list(self._node.connections.keys())

        # we should only have one connection at this point
        self.assertEquals(len(connections), 1)

        # our socket should be in the nodes connection list
        self.assertTrue(sock_raddr in [x.getsockname() for x in connections])

    def test_msg_receive(self) -> None:

        # connect for sending
        self._sock.connect(("localhost", self._node._msg_port))

        # wait for our node to be ready to receive messages
        ready_to_write: Union[List[socket.socket], None] = None
        ready_to_read: Union[List[socket.socket], None] = None
        while (ready_to_read is None) or (ready_to_write is None):
            ready_to_read, ready_to_write, _ = select.select(list(self._node.connections.keys()), 
                                                             [self._sock], 
                                                             [], 0)

        client: Register_pb2.ClientMetadata = Register_pb2.ClientMetadata()
        client.addr = self.host
        client.port = self.port
        client_string: bytes = client.SerializeToString()
        
        message_type: bytes = client.DESCRIPTOR.full_name.encode()

        data_len = struct.pack("H", len(message_type) + len(client_string))
        test_message: bytearray = b""
        test_message += data_len
        test_message += message_type
        test_message += client_string

        # # test_message: str = "TEST123\n"
        if self._sock in ready_to_write:
            self._sock.sendall(test_message)

        # there should be a single connection
        self._node.wait_for_connections(blocking=True)
        self.assertEquals(len(self._node.connections), 1)
        connection: Connection = list(self._node.connections.values())[0]

        connection.wait_for_inbound(blocking=True)

        # there should be only one message in the inbound for our connection...
        self.assertEquals(connection.inbound.qsize(), 1)

        # ... and that message should match the one we sent
        message: str = connection.inbound.get(block=False)
        self.assertEquals(test_message[2:], message) # strip data_len from test_message

    def test_msg_send(self) -> None:

        pass


class Test_Node_IPC(unittest.TestCase):

    host: str = "localhost"
    port: int = 50051

    def setUp(self) -> None:

        self._server: grpc.Server = grpc.server(
            thread_pool=futures.ThreadPoolExecutor(max_workers=10)
        )
        self._server.add_insecure_port(f'[::]:{self.port}')
        
        self._clients: Dict[str,Client] = {}
        self._reg_servicer: RegisterServicer = RegisterServicer(clients=self._clients)
        add_RegisterServicer_to_server(
            servicer=self._reg_servicer,
            server=self._server
        )
        
        self._topics: Dict[str,Topic] = {}
        self._topic_servicer: TopicServicer = TopicServicer(
            topics=self._topics
        )
        add_TopicServicer_to_server(
            servicer=self._topic_servicer,
            server=self._server
        )

        self._server.start()
        
        self._node_A: Node = init_node(name="node_A", address=("localhost", 50510))
        self._node_B: Node = init_node(name="node_B", address=("localhost", 50610))
        
    def tearDown(self) -> None:
        
        self._node_A.cleanup()
        self._node_B.cleanup()
        
        stopping: threading.Event = self._server.stop(grace=None)
        stopping.wait()

    @unittest.skip('for now')
    def test_introductions(self) -> None:

        self._node_B.introduce(other_client=self._node_A._name,
                               conn=self._node_A._msg_socket)
        
        self.assertTrue(self._node_B.get_connection(name=self._node_A._name) is not None)
        
        # wait for the message to be sent...
        self._node_B.get_connection(name="node_A").wait_for_outbound()
        # ... and for the message to be processed by the receiver... 
        self._node_A.wait_for_connections()
        self._node_A.wait_for_initialized()

        # and now the introduction should be complete
        self.assertTrue(self._node_A.get_connection(name=self._node_B._name) is not None)
        self.assertTrue(self._node_A.get_connection("node_B").initialized)
        self.assertTrue(self._node_B.get_connection("node_A").initialized)
    
    @unittest.skip('for now')
    def test_hashing_sockets(self) -> None:

        sock_B_hash: int = hash(self._node_B._msg_socket)
        print(self._node_B._msg_socket)
        print(sock_B_hash)

        remote_b_socket: socket.socket = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM
        )
        remote_b_socket.connect((
            self._node_B._msg_socket.getsockname()[0],
            self._node_B._msg_socket.getsockname()[1]
        ))

        remote_B_hash: int = hash(remote_b_socket)
        print(remote_B_hash)

    def test_subscribe_to_unpublished(self) -> None:

        result: bool = self._node_B.subscribe(
            topic_name="test_topic",
            message_type="test",
            callback_fn=None
        )

        self.assertTrue(result)

        # make sure that the servicer has the right info

        # make sure that the node has the right info

    def test_subscribe_to_advertised(self) -> None:

        # first, advertise a topic with node_A
        result: bool = self._node_A.advertise_topic(
            topic_name="test_topic",
            message_type="test"
        )
        self.assertTrue(result)

        # once that topic is advertised, attempt to subscribe with B
        result: bool = self._node_B.subscribe(
            topic_name="test_topic",
            message_type="test",
            callback_fn=None
        )
        self.assertTrue(result)
        
        self.assertFalse(self._node_B._subscriptions.get("test_topic", None) is None)
        while self._node_B._subscriptions.get("test_topic", None).confirmed == False:
            continue
        
        self.assertTrue(True)

    def test_advertise_to_unsubscribed(self) -> None:

        result: bool = self._node_A.advertise_topic(
            topic_name="test_topic",
            message_type="test"
        )

        self.assertTrue(result)

        # make sure that the servicer has the right info

        # make sure that the node has the right info

if __name__ == '__main__':
    unittest.main(warnings='ignore')