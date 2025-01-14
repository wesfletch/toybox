#!/usr/bin/env python3

import unittest

import concurrent.futures as futures
import errno
import grpc
from queue import Queue
import select
import socket
import struct
import sys
import threading

# sys.path.append('/home/dev/toybox')
from toybox_core.connection import (
    Connection,
    Subscriber, 
    Publisher
)
from toybox_msgs.core.Test_pb2 import TestMessage
from toybox_msgs.core.Node_pb2 import InformConfirmation

from typing import Dict, Union, List

class Test_Publisher(unittest.TestCase):

    host: str = "localhost"
    port: int = 50089

    topic_name: str = "test_topic"
    message_type: str = TestMessage.DESCRIPTOR.full_name

    def setUp(self) -> None:
        
        self._publisher: Publisher = Publisher(
            topic_name=self.topic_name,
            message_type=self.message_type,
            host=self.host,
            port=self.port
        )

    def tearDown(self) -> None:
        
        if self._publisher is not None:
            self._publisher.shutdown = True

        self._publisher._spin_shutdown.wait()
        self._publisher._listen_shutdown.wait()

    def test_constructor(self) -> None:
        self.assertTrue(True)

    def test_publisher_socket(self) -> None:

        sock, host = self._publisher.sock.getsockname()

        test_sock: socket.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        status: int = test_sock.connect_ex(('', host))
        
        try:
            self.assertTrue(status == 0)
        except AssertionError as e:
            print(f"Connection error <{status}>: {errno.errorcode[status]}")
            raise e

    def test_unpack_message(self) -> None:
        
        string_data: str = "testy mctesterson"
        test_message: TestMessage = TestMessage(test_string=string_data)

        message_bytes: bytes = Connection.pack_message(message=test_message)

        message_type, message_data = Connection.split_message(message_bytes)
        
        # strip the "length" bytes off of the packed message
        message_type = message_type[2:]
        self.assertEqual(message_type, self.message_type)

        message: TestMessage = Connection.unpack_message(TestMessage, message_data)

        self.assertEqual(string_data, message.test_string)

    def test_enqueue_message_with_publish(self) -> None:

        string_data: str = "testy mctesterson"
        test_message: TestMessage = TestMessage(test_string=string_data)

        self._publisher.publish(test_message)
        
        message_bytes: bytes = self._publisher.outbound.get(block=True)
        message_type, message_data = Connection.split_message(message_bytes)
        message: TestMessage = Connection.unpack_message(TestMessage, message_data)

        self.assertEqual(message.test_string, string_data)

    def test_fail_to_publish_invalid_types(self) -> None:

        invalid_message: InformConfirmation = InformConfirmation(return_code=0, status="test")
        self.assertRaises(Exception, self._publisher.publish, invalid_message)

if __name__ == '__main__':
    unittest.main(warnings='ignore')