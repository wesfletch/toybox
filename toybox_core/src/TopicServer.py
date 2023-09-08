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
    Confirmation,
    PublisherList,
    SubscriberList,
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
    publishers: List[str] = field(default_factory=list)
    subscribers: List[str] = field(default_factory=list)

    callbacks: List[Callable] = field(default_factory=list)

class TopicServicer(TopicServicer):

    def __init__(self, topics: Dict[str, Topic]):
        self._topics = topics

    def AdvertiseTopic(
        self, 
        request: TopicDefinition, 
        context
    ) -> Confirmation:
        """
        IN: TopicDefiniton
        OUT: Confirmation
        """

        uuid: str = request.uuid
        topic_name: str = request.topic_name
        message_type: str = request.message_type

        conf: Confirmation = Confirmation()
        conf.return_code = 0
        conf.topic.CopyFrom(request)
        conf.status: str = ""

        # check if this topic already exists
        if self._topics.get(topic_name) is not None:
            # for now, don't allow more than one publisher on a given topic
            if len(self._topics.get(topic_name).publishers) > 0:
                conf.return_code = 1
                conf.status = "Topic already advertised."
                return Confirmation(return_code=1,
                                    topic=request,
                                    status="Topic already advertised.")
            # if we have preemptive subscribers, we need to inform the publisher
            elif self._topics.get(topic_name).subscribers is not None:
                subscribed: List[str] = [x for x in self._topics.get(topic_name).subscribers]
                subscribers: SubscriberList = SubscriberList(subscriber_id=subscribed)
                conf.subscribers.CopyFrom(subscribers)
        else:   
            self._topics[topic_name] = Topic(name=topic_name,
                                            message_type=message_type,
                                            publishers=[uuid])
            conf.status = f"Topic <{topic_name}> advertised successfully."
        
        # print(self._topics)

        return conf
    
    def SubscribeTopic(
        self, 
        request: TopicDefinition, 
        context
    ) -> Confirmation:
        
        uuid: str = request.uuid
        topic_name: str = request.topic_name
        message_type: str = request.message_type

        # build our confirmation
        conf: Confirmation = Confirmation()
        conf.topic.CopyFrom(request)
        conf.return_code: int = 0

        if self._topics.get(topic_name) is None:
            self._topics[topic_name] = Topic(name=topic_name,
                                             message_type=message_type,
                                             subscribers=[uuid])
        else:
            if uuid in self._topics[topic_name].publishers:
                conf.return_code = 1
                conf.status = "You can't subscribe to a topic you're also publishing, dork."  
            else:
                self._topics[topic_name].subscribers.append(uuid)
                
                # send any declared publishers of this topic back to the subscriber
                publishers = PublisherList(
                    publisher_id=[x for x in self._topics.get(topic_name).publishers],
                )
                conf.publishers.CopyFrom(publishers)

        # print(self._topics)

        return conf


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



channel: grpc.insecure_channel = grpc.insecure_channel('localhost:50051')
stub: TopicStub = TopicStub(channel=channel)

def advertise_topic_rpc(
    client_name: str,
    topic_name: str,
    message_type: str,
) -> bool:

    advertise_req: TopicDefinition = TopicDefinition(
        uuid=client_name,
        topic_name=topic_name,
        message_type=message_type,
    )

    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    # print(conf)
    return (conf.return_code == 0)

def subscribe_topic_rpc(
    client_name: str,
    topic_name: str,
    message_type: str,
) -> Union[List[str], None]:
    
    subscribe_req: TopicDefinition = TopicDefinition(
        uuid=client_name,
        topic_name=topic_name,
        message_type=message_type,
    )

    conf: Confirmation = stub.SubscribeTopic(request=subscribe_req)

    if not conf.HasField("client_list"):
        return None
    elif conf.WhichOneof("client_list") != "publishers":
        return None
    else:
        return [x for x in conf.publishers.publisher_id]

def main():

    # channel: grpc.insecure_channel = grpc.insecure_channel('localhost:50051')
    # stub: TopicStub = TopicStub(channel=channel)

    advertise_req: TopicDefinition = TopicDefinition(
        uuid="1",
        topic_name="butts",
        message_type="butts"
    )
    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    print(conf)

    subscribe_req: TopicDefinition = TopicDefinition(
        uuid="test_sub",
        topic_name="butter",
        message_type="butts",
    )
    sub_conf: Confirmation = stub.SubscribeTopic(request=subscribe_req)
    print(sub_conf)

    advertise_req= TopicDefinition(
        uuid="1",
        topic_name="buttest",
        message_type="butter",
    )
    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    print(conf)

if __name__ == "__main__":
    main()