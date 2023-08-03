#!/usr/bin/env python3

import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable

import concurrent.futures as futures
import grpc

# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')

from toybox_msgs.core.Topic_pb2 import (
    TopicDefinition,
    Confirmation
)
from toybox_msgs.core.Topic_pb2_grpc import (
    TopicServicer, 
    TopicStub,
    add_TopicServicer_to_server
)
from toybox_core.src.RegisterServer import Client


@dataclass
class Topic():
    name: str
    message_type: str 
    publishers: List[Client] = field(default_factory=list)
    subscribers: List[Client] = field(default_factory=list)


class TopicServicer(TopicServicer):

    def __init__(self, topics: Dict[str, Topic]):
        self._topics = topics

    def AdvertiseTopic(self, request: TopicDefinition, context) -> Confirmation:
        """
        IN: TopicDefiniton
        OUT: Confirmation
        """

        uuid: str = request.uuid
        topic_name: str = request.topic_name
        message_type: str = request.message_type

        # check if this topic already exists
        if self._topics.get(topic_name) is not None:
            return Confirmation(return_code=1,
                                topic=request,
                                status="Topic already advertised.")
        
        self._topics[topic_name] = Topic(name=topic_name,
                                         message_type=message_type,
                                         publishers=[uuid])
    
        return Confirmation(return_code=0, 
                            topic=request)

    def SubscribeTopic(self, request: TopicDefinition, context):
        
        uuid: str = request.uuid
        topic_name: str = request.topic_name
        message_type: str = request.message_type

        if self._topics.get(topic_name) is None:
            self._topics[topic_name] = Topic(name=topic_name,
                                             message_type=message_type,
                                             subscribers=[uuid])
        else:
            self._topics[topic_name].subscribers.append(uuid)

        return


class TopicServer():

    def __init__(self) -> None:

        self._topics: Dict[str, Topic] = {}
        self._servicer: TopicServicer = TopicServicer(topics=self._topics)

    def serve(self):
        
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_TopicServicer_to_server(
            self._servicer, 
            self._server
        )

        self._server.add_insecure_port('[::]:50051')
        
        self._server.start()
        # self._server.wait_for_termination()


def main():

    channel: grpc.insecure_channel = grpc.insecure_channel('localhost:50051')
    stub: TopicStub = TopicStub(channel=channel)

    advertise_req: TopicDefinition = TopicDefinition(
        uuid="1",
        topic_name="butts",
        message_type="butts"
    )
    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    print(conf)

    advertise_req= TopicDefinition(
        uuid="1",
        topic_name="butter",
        message_type="butter"
    )
    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    print(conf)

if __name__ == "__main__":
    main()