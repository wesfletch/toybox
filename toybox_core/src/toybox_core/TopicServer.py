#!/usr/bin/env python3

from typing import Dict, List, Tuple, Union
import uuid

import concurrent.futures as futures
import grpc
from google.protobuf.message import Message

from toybox_msgs.core.Client_pb2_grpc import ClientStub
from toybox_msgs.core.Client_pb2 import (
    InformConfirmation,
    TopicPublisherInfo
)
from toybox_msgs.core.Topic_pb2 import (
    AdvertiseRequest,
    Confirmation,
    SubscriptionRequest,
    SubscriptionResponse,
    TopicList
)
from toybox_msgs.core.Topic_pb2_grpc import (
    TopicServicer, 
    TopicStub,
)
from toybox_msgs.core.Null_pb2 import Null as NullMsg

from toybox_core.RegisterServer import Client
from toybox_core.Logging import LOG
from toybox_core.Topic import Topic


class TopicRPCServicer(TopicServicer):

    def __init__(
        self, 
        topics: Dict[str, Topic],
        clients: Dict[str, Client],
    ) -> None:
        self._topics = topics
        self._clients = clients

    def AdvertiseTopic(
        self, 
        request: AdvertiseRequest, 
        context: grpc.ServicerContext,
    ) -> Confirmation:
        """
        IN: AdvertiseRequest
        OUT: Confirmation
        """

        advertiser_id: str = request.publisher.publisher_id
        advertiser_host: str = request.publisher.publisher_host
        advertiser_port: int = request.publisher.topic_port
        topic_name: str = request.topic_def.topic_name
        message_type: str = request.topic_def.message_type

        conf: Confirmation = Confirmation()
        conf.uuid = "-"
        conf.return_code = 0
        conf.status = ""

        # Check if this topic already exists
        topic: Topic | None = self._topics.get(topic_name, None)
        if topic is None:
            # Topic doesn't exist yet, so all we need to do is create a new Topic object
            # to represent it.
            self._topics[topic_name] = Topic(
                name=topic_name,
                message_type=message_type,
                publishers={advertiser_id: (advertiser_host, advertiser_port)})
            conf.status = f"Topic <{topic_name}> from client <{advertiser_id}> advertised successfully."
            return conf
        
        # The topic already exists, meaning it's been advertised by a Publisher
        # and/or been subscribed to by a Subscriber.
        
        # TODO: I think I'd rather not allow two topics to share a name at all. But we'll see...
        if advertiser_id in topic.publishers.keys():
            # Don't allow a publisher to re-declare a topic it's already declared.
            conf.return_code = 1
            conf.status = f"multiple advertise for topic <{topic_name}> by publisher <{advertiser_id}>"
            return conf
        elif topic.message_type != message_type:
            # Don't allow two topics to share a name, but not a type
            conf.return_code = 2
            conf.status = f"declared message type <{message_type}> \
                doesn't match previously advertised <{topic.message_type}"
            return conf
        
        # If we've gotten to this point, the topic DOES exist already, and the topic definition
        # we were given by the RPC matches it. We're clear to add this new publisher.
        topic.publishers[advertiser_id] = (advertiser_host, advertiser_port)
        conf.status = f"Topic <{topic_name}> advertised successfully."
           
        # Finally, we need to make sure that any subscribers that were subscribed to this topic BEFORE
        # this publisher advertised it are informed that there's a new publisher.
        for subscriber_name in topic.subscribers:
            # Special case: a node advertises a topic that it's also subscribed to.
            # TODO: For now, skip it. May need to actually handle this in the future.
            if subscriber_name == advertiser_id:
                continue

            subscriber: Client | None = self._clients.get(subscriber_name, None)
            assert subscriber is not None

            # TODO: I'm calling an RPC from the body of another RPC. What are the 
            # ramifications of that?
            stub: ClientStub = subscriber.get_stub()

            topic_pub: TopicPublisherInfo = TopicPublisherInfo()
            topic_pub.topic_def.CopyFrom(request.topic_def)
            topic_pub.publisher.CopyFrom(request.publisher)
            inform_conf: InformConfirmation = stub.InformOfPublisher(topic_pub, timeout=1.0)

            if inform_conf.return_code != 0:
                conf.status = "Failed to inform subscribers of new publisher."
                conf.status = 1

        return conf
    
    def DeAdvertiseTopic(self, request, context) -> Confirmation:
        raise NotImplementedError
    
    def SubscribeTopic(
        self, 
        request: SubscriptionRequest, 
        context: grpc.ServicerContext,
    ) -> SubscriptionResponse:

        subscriber_id: str = request.subscriber_id
        topic_name: str = request.topic_def.topic_name
        message_type: str = request.topic_def.message_type

        # build our response
        response: SubscriptionResponse = SubscriptionResponse()
        response.conf.return_code = 0
        response.topic_def.CopyFrom(request.topic_def)

        topic: Topic | None = self._topics.get(topic_name, None) 
        if topic is None:
            # The topic hasn't been advertised by any publishers, or subscribed to
            # by any other subscribers.
            self._topics[topic_name] = Topic(
                name=topic_name,
                message_type=message_type,
                subscribers=[subscriber_id])
        else:
            # The topic exists, and may or may not already have publishers
            # associated with it.
            topic.subscribers.append(subscriber_id)

            for publisher_id, publisher_info in topic.publishers.items():
                response.publisher_list.add(
                    publisher_id=publisher_id,
                    publisher_host=publisher_info[0],
                    topic_port=publisher_info[1])

        return response
    
    def ListTopics(
        self,
        request: NullMsg,
        context: grpc.ServicerContext,
    ) -> TopicList:

        response: TopicList = TopicList()

        for topic_name in self._topics.keys():
            topic: Topic = self._topics[topic_name]
            response.topics.append(topic.to_msg())

        return response


channel: grpc.insecure_channel = grpc.insecure_channel('[::]:50051')
stub: TopicStub = TopicStub(channel=channel)

def advertise_topic_rpc(
    client_name: str,
    client_host: str,
    topic_port: int,
    topic_name: str,
    message_type: Message,
) -> bool:

    advertise_req: AdvertiseRequest = AdvertiseRequest()
    advertise_req.publisher.publisher_id = client_name
    advertise_req.publisher.publisher_host = client_host
    advertise_req.publisher.topic_port = topic_port
    advertise_req.topic_def.topic_name = topic_name
    advertise_req.topic_def.message_type = message_type.DESCRIPTOR.full_name

    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    return (conf.return_code == 0)


def subscribe_topic_rpc(
    subscriber_id: str,
    topic_name: str,
    message_type: str,
) -> List[Tuple[str,str,int]]:

    subscribe_req: SubscriptionRequest = SubscriptionRequest()
    subscribe_req.subscriber_id = subscriber_id
    subscribe_req.topic_def.topic_name = topic_name
    subscribe_req.topic_def.message_type = message_type

    response: SubscriptionResponse = stub.SubscribeTopic(request=subscribe_req)

    returned: List[Tuple[str,str,int]] = []
    for publisher in response.publisher_list:
        returned.append((publisher.publisher_id, publisher.publisher_host, publisher.topic_port))

    return returned


def list_topics_rpc() -> List[Topic]:

    returned: List[Topic] = []

    request: NullMsg = NullMsg()
    response: TopicList = stub.ListTopics(request=request)
    
    for topic_def in response.topics:
        topic: Topic = Topic(name=topic_def.topic_name, message_type=topic_def.message_type)
        returned.append(topic)

    return returned