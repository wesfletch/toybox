#!/usr/bin/env python3

import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable

import grpc
# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')
# from toybox_msgs.core import Topic_pb2_grpc

from toybox_msgs.core.Topic_pb2 import (
    TopicDefinition,
    Confirmation
)
from toybox_msgs.core.Topic_pb2_grpc import (
    TopicServicer, 
)

from topic import Topic

class TopicServicer(TopicServicer):

    def __init__(self, topics: Dict[str, Topic]):
        self._topics = topics

    def AdvertiseTopic(self, request: TopicDefinition, context) -> Confirmation:
        """
        IN: TopicDefiniton
        OUT: Confirmation
        """

        print(request)
        uuid: str = request.uuid
        topic_name: str = request.topic_name
        message_type: str = request.message_type

        # check if this topic already exists
        if self._topics.get(topic_name) is None:
            return 

        pass
    
    def SubscribeTopic(self, request, context):
        pass


def main():

    topics: Dict[str, Topic] = {}
    servicer: TopicServicer = TopicServicer(topics=topics)

    advertise_req: TopicDefinition = TopicDefinition(
        uuid="1",
        topic_name="butts",
        message_type="butts"
    )

    servicer.AdvertiseTopic(request=advertise_req, context=None)

    print(topics)

if __name__ == "__main__":
    main()