#!/usr/bin/env python3

import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable
import uuid

import concurrent.futures as futures
import grpc

# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')

from toybox_msgs.core.Topic_pb2 import (
    AdvertiseRequest,
    TopicDefinition,
    Confirmation,
    SubscribeResponse,
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

    confirmed: bool = False

class TopicServicer(TopicServicer):

    def __init__(self, topics: Dict[str, Topic]):
        self._topics = topics

    def AdvertiseTopic(
        self, 
        request: AdvertiseRequest, 
        context
    ) -> Confirmation:
        """
        IN: AdvertiseRequest
        OUT: Confirmation
        """
        advertiser_id: str = request.client_id
        topic_name: str = request.topic_def.topic_name
        message_type: str = request.topic_def.message_type

        conf: Confirmation = Confirmation()
        conf.uuid = "-"
        conf.return_code = 0
        conf.status: str = ""

        # check if this topic already exists
        if self._topics.get(topic_name) is not None:
            # for now, don't allow more than one publisher on a given topic
            if len(self._topics.get(topic_name).publishers) > 0:
                return Confirmation(return_code=1,
                                    uuid="-",
                                    status="Topic already advertised.")
            # # if we have preemptive subscribers, we need to inform the publisher
            # elif self._topics.get(topic_name).subscribers is not None:
            #     subscribed: List[str] = [x for x in self._topics.get(topic_name).subscribers]
            #     subscribers: SubscriberList = SubscriberList(subscriber_id=subscribed)
            #     conf.subscribers.CopyFrom(subscribers)
        else:   
            self._topics[topic_name] = Topic(name=topic_name,
                                            message_type=message_type,
                                            publishers=[advertiser_id])
            conf.status = f"Topic <{topic_name}> advertised successfully."
        
        return conf
    
    def SubscribeTopic(
        self, 
        request: TopicDefinition, 
        context
    ) -> SubscribeResponse:
        """
        _summary_

        Args:
            request (TopicDefinition): _description_
            context (_type_): _description_

        Returns:
            Confirmation: _description_
        """
        uuid: str = request.uuid
        topic_name: str = request.topic_name
        message_type: str = request.message_type

        # build our response
        response: SubscribeResponse = SubscribeResponse()
        response.confirmation.uuid = uuid
        response.confirmation.return_code: int = 0

        if self._topics.get(topic_name) is None:
            self._topics[topic_name] = Topic(
                name=topic_name,
                message_type=message_type,
                subscribers=[uuid]
            )
        else:
            self._topics[topic_name].subscribers.append(uuid)
            
            # send any declared publishers of this topic back to the subscriber
            publishers = [x for x in self._topics.get(topic_name).publishers]         
            response.publisher_list.extend(publishers)

        return response


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

    advertise_req: AdvertiseRequest = AdvertiseRequest()
    advertise_req.client_id = client_name
    advertise_req.topic_def.uuid = str(uuid.uuid4())
    advertise_req.topic_def.topic_name = topic_name
    advertise_req.topic_def.message_type = message_type

    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    return (conf.return_code == 0)

def subscribe_topic_rpc(
    topic_name: str,
    message_type: str,
) -> Union[List[str], None]:
    
    subscribe_req: TopicDefinition = TopicDefinition(
        uuid=str(uuid.uuid4()),
        topic_name=topic_name,
        message_type=message_type,
    )

    response: SubscribeResponse = stub.SubscribeTopic(request=subscribe_req)

    return [x for x in response.publisher_list]

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