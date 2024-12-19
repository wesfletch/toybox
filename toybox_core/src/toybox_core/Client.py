#!/usr/bin/env python3

"""
FILE: Client.py
DESC: Functions intended to be used by the 'clients' of this library
      when interfacing with tbx.
"""

from typing import Tuple

from toybox_core.Logging import LOG
from toybox_core.Node import Node
from toybox_core.Connection import get_available_port
from toybox_core.RegisterServer import register_client_rpc, deregister_client_rpc

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
