#!/usr/bin/env python3

from dataclasses import dataclass, field
from google.protobuf.message import Message
from typing import Callable

from toybox_msgs.core.Topic_pb2 import TopicDefinition

@dataclass
class Topic():
    name: str
    message_type: Message
    publishers: dict[str, tuple[str,int]] = field(default_factory=dict) # {client, addr}
    subscribers: list[str] = field(default_factory=list)

    callbacks: list[Callable] = field(default_factory=list)

    confirmed: bool = False

    def to_msg(self) -> TopicDefinition:
        return TopicDefinition(
            topic_name=self.name, 
            message_type=self.message_type)
