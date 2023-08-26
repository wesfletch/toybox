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
)
from toybox_msgs.core.Topic_pb2 import (
    TopicDefinition,
)
from toybox_core.src.TopicServer import (
    Topic
)

from typing import Dict, Union, List


class Test_TopicServicer(unittest.TestCase):
    pass

if __name__ == '__main__':
    unittest.main()