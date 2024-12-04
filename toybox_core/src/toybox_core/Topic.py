#!/usr/bin/env python3

from dataclasses import dataclass, field
from google.protobuf.message import Message
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable

from toybox_msgs.core.Topic_pb2 import TopicDefinition

@dataclass
class Topic():
    name: str
    message_type: str 
    publishers: Dict[str, Tuple[str,int]] = field(default_factory=dict) # {client, addr}
    subscribers: List[str] = field(default_factory=list)

    callbacks: List[Callable] = field(default_factory=list)

    confirmed: bool = False

    def to_msg(self) -> TopicDefinition:
        print(f"MESSAGE_TYPE: {self.message_type}")
        return TopicDefinition(
            topic_name=self.name, 
            message_type=self.message_type)