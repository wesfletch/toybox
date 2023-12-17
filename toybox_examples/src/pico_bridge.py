#!/usr/bin/env python3

import time
from typing import Union

import toybox_core as tbx
from toybox_core import Node, Publisher

from toybox_msgs.core.Test_pb2 import TestMessage

def test_callback(self, message: TestMessage) -> None:
    print(message.test_string)

def main() -> None:

    node: Node = tbx.init_node("pico_bridge")
    test_pub: Union[Publisher,None] = node.advertise(
        topic_name="/test",
        message_type=TestMessage)
    if not test_pub:
        return

    # TODO: this doesn't actually work yet
    while not tbx.is_shutdown():
        time.sleep(1)
        test_pub.publish(TestMessage(test_string="test test test"))

if __name__ == "__main__":
    main()