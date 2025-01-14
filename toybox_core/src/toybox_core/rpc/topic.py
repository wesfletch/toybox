#!/usr/bin/env python3

import threading
import grpc
from google.protobuf.message import Message
from queue import Queue

from toybox_msgs.core.Topic_pb2 import (
    AdvertiseRequest,
    Confirmation,
    SubscriptionRequest,
    SubscriptionResponse,
    TopicList
)
from toybox_msgs.core.Topic_pb2_grpc import TopicServicer, TopicStub
from toybox_msgs.core.Null_pb2 import Null as NullMsg

from toybox_core.client import Client
from toybox_core.logging import LOG
from toybox_core.topic import Topic


class TopicRPCServicer(TopicServicer):

    def __init__(
        self, 
        topics: dict[str, Topic],
        clients: dict[str, Client],
        announcements: Queue[tuple[str,str]]
    ) -> None:
        self._topics = topics
        self._clients = clients

        self._announcements = announcements

        self._topic_lock: threading.Lock = threading.Lock()

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

        LOG("DEBUG", f"Received AdvertiseTopic request from {advertiser_id} at {advertiser_host}:{advertiser_port}:\n topic_name: {topic_name}, message_type: {message_type}")

        # Check if this topic already exists
        topic: Topic | None = None
        with self._topic_lock:
            topic = self._topics.get(topic_name, None)
        if topic is None:
            LOG("DEBUG", f"Creating new topic {topic_name} with type {message_type}")
            # Topic doesn't exist yet, so all we need to do is create a new Topic object
            # to represent it.
            self._topics[topic_name] = Topic(
                name=topic_name,
                message_type=message_type,
                publishers={advertiser_id: (advertiser_host, advertiser_port)})
            conf.status = f"Topic <{topic_name}> from client <{advertiser_id}> advertised successfully."
            return conf
        
        # The topic already exists, meaning it's previously been advertised by a Publisher
        # and/or been subscribed to by a Subscriber.
        LOG("DEBUG", f"Topic {topic_name} already exists.")
        
        # TODO: I think I'd rather not allow two topics to share a name at all. But we'll see...
        if advertiser_id in topic.publishers.keys():
            LOG("DEBUG", f"Rejecting AdvertiseTopic request from {advertiser_id} for {topic_name}: Advertiser already declared this topic.")
            # Don't allow a publisher to re-declare a topic it's already declared.
            conf.return_code = 1
            conf.status = f"multiple advertise for topic <{topic_name}> by publisher <{advertiser_id}>"
            return conf
        elif topic.message_type != message_type:
            LOG("DEBUG", f"Rejecting AdvertiseTopic request from {advertiser_id} for {topic_name}: Message type doesn't match.")
            # Don't allow two topics to share a name, but not a type
            conf.return_code = 2
            conf.status = f"declared message type <{message_type}> \
                doesn't match previously advertised <{topic.message_type}"
            return conf
        
        # If we've gotten to this point, the topic DOES exist already, and the topic definition
        # we were given by the RPC matches it. We're clear to add this new publisher.
        topic.publishers[advertiser_id] = (advertiser_host, advertiser_port)
        conf.status = f"Topic <{topic_name}> advertised successfully."
        LOG("DEBUG", f"Added new publisher <{advertiser_id}> for topic {topic_name}")
        
        # Defer informing subscribers of this new publisher until after this RPC completes.
        # This is a (kinda) dirty hack to get around race conditions between SubscribeTopic and AdvertiseTopic.
        # The client nodes should be smart enough to deal with this.
        LOG("DEBUG", f"Deferring announcement for <{topic_name}> from publisher <{advertiser_id}>")
        self._announcements.put((advertiser_id, request.topic_def.topic_name))

        LOG("DEBUG", f"AdvertiseTopic request for <{topic_name}> complete.")
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

        LOG("DEBUG", f"Received SubscribeTopic request from {subscriber_id}: topic == <{topic_name}>, message_type == <{message_type}>")

        topic: Topic | None = None
        with self._topic_lock:
            topic = self._topics.get(topic_name, None) 
        if topic is None:
            LOG("DEBUG", f"Topic {topic_name} with type {message_type} not advertised yet. Creating new topic.")
            # The topic hasn't been advertised by any publishers, or subscribed to
            # by any other subscribers.
            self._topics[topic_name] = Topic(
                name=topic_name,
                message_type=message_type,
                subscribers=[subscriber_id])
        else:
            # The topic exists, and may or may not already have publishers
            # associated with it.
            if message_type != topic.message_type:
                LOG("WARN", f"Subscriber requested message type {message_type} doesn't match topic definition {topic.message_type}")
                response.conf.return_code = 1
                return response

            LOG("DEBUG", f"Adding subscriber <{subscriber_id}> to topic <{topic_name}>")
            topic.subscribers.append(subscriber_id)

            for publisher_id, publisher_info in topic.publishers.items():
                response.publisher_list.add(
                    publisher_id=publisher_id,
                    publisher_host=publisher_info[0],
                    topic_port=publisher_info[1])

        LOG("DEBUG", f"SubscribeTopic request from {subscriber_id} FINISHED")

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
) -> list[tuple[str,str,int]]:

    subscribe_req: SubscriptionRequest = SubscriptionRequest()
    subscribe_req.subscriber_id = subscriber_id
    subscribe_req.topic_def.topic_name = topic_name
    subscribe_req.topic_def.message_type = message_type

    response: SubscriptionResponse = stub.SubscribeTopic(request=subscribe_req)

    returned: list[tuple[str,str,int]] = []
    for publisher in response.publisher_list:
        returned.append((publisher.publisher_id, publisher.publisher_host, publisher.topic_port))

    return returned


def list_topics_rpc() -> list[Topic]:

    returned: list[Topic] = []

    request: NullMsg = NullMsg()
    response: TopicList = stub.ListTopics(request=request)
    
    for topic_def in response.topics:
        topic: Topic = Topic(name=topic_def.topic_name, message_type=topic_def.message_type)
        returned.append(topic)

    return returned