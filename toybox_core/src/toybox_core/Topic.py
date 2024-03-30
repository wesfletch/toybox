#!/usr/bin/env python3

from dataclasses import dataclass, field
from google.protobuf.message import Message
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable

@dataclass
class Topic():
    name: str
    message_type: Message 
    publishers: Dict[str, Tuple[str,int]] = field(default_factory=dict) # {client, addr}
    subscribers: List[str] = field(default_factory=list)

    callbacks: List[Callable] = field(default_factory=list)

    confirmed: bool = False