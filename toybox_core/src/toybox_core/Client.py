#!/usr/bin/env python3

"""
FILE: Client.py
DESC: Functions intended to be used by the 'clients' of this library
      when interfacing with tbx.
"""

import atexit
import threading
from typing import List, Union, Tuple

from toybox_core.Logging import LOG
from toybox_core.Node import Node
from toybox_core.Connection import get_available_port
from toybox_core.RegisterServer import register_client_rpc, deregister_client_rpc
from toybox_core.TopicServer import advertise_topic_rpc, subscribe_topic_rpc

def deinit_node(
    name: str,
    node: Node | None
) -> None:
    
    LOG("DEBUG", f"De-initializing node <{name}>")
    result: bool = deregister_client_rpc(name=name)
    
def init_node(
    name: str,
    address: Tuple[str,int] | None = None,
    log_level: str | None = None,
    autostart: bool = True
) -> Node:
    """
    Create a toybox node with the given name.

    Returns:
        _type_: _description_
    """

    if address is None:
        host: str = "localhost"
        port: int = get_available_port(host="localhost")
    else:
        host, port = address
    
    node: Node = Node(
        name=name, 
        host=host, 
        port=port,
        log_level=log_level,
        autostart=autostart
    )
    LOG("DEBUG", f"Initialized Node <{name}> with address <{host},{port}>")

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
    
    # TODO: obviously this was left unfinished...
    #       What was I going to do here?
    for publisher in publishers:
        pass
