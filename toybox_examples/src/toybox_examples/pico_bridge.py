#!/usr/bin/env python3

import threading
import time
from typing import List

import toybox_core as tbx
from toybox_core import Node, Publisher
from toybox_core.launchable import Launchable
from toybox_msgs.core.Test_pb2 import TestMessage


class PicoBridge(Launchable):
    
    def __init__(
        self, 
        name: str
    ) -> None:
        
        self._name = name
        self._node: tbx.Node.Node = tbx.init_node(
            name=self._name,
            log_level="INFO")

        self._publisher: Publisher | None

    def pre_launch(self) -> bool:
        self._publisher = self._node.advertise(
            topic_name="/test",
            message_type=TestMessage
        )
        if self._publisher is None:
            return False
        else:
            return True
        
    def launch(self) -> bool:
        freq: int = 10
        while not self._node.is_shutdown():
            time.sleep(1/freq)
            self._publisher.publish(
                TestMessage(test_string="test test test")
            )
        return True

    def shutdown(self) -> None:
        self._node.shutdown()

class Listener(Launchable):

    def __init__(
        self, 
        name: str,
        topic: str | None = None
    ) -> None:
        
        self._name = name
        self._node: tbx.Node.Node = tbx.Node.Node(
            name=self._name,
            log_level="INFO",
            autostart=False)

        self.topic = topic if topic is not None else "/test"

        self._publisher: tbx.Publisher

    def callback(self, message: TestMessage) -> None:
        print(message)

    def pre_launch(self) -> bool:
        self._node.start()
        self._subscribed: bool = self._node.subscribe(
            topic_name=self.topic,
            message_type=TestMessage,
            callback_fn=self.callback)
        if not self._subscribed:
            return False
        
        self._publisher = self._node.advertise(
            topic_name="/test",
            message_type=TestMessage)
        if self._publisher is None:
            return False

        return True
        
    def launch(self) -> bool:
        freq: int = 10
        while not self._node.is_shutdown():
            time.sleep(1/freq)
        return True
    
    def post_launch(self) -> bool:
        return True
    
    def shutdown(self) -> None:
        self._node.shutdown()

