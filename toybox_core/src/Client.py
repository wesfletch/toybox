#!/usr/bin/env python3

from abc import ABC, abstractmethod
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

from toybox_core.src.Node import Node
from toybox_core.src.Connection import (
    get_available_port
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
from toybox_msgs.core.Topic_pb2 import (
    SubscriberList,
    TopicDefinition,
)

import toybox_msgs.core.Topic_pb2 as Topic_pb2

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