#!/usr/bin/env python3

from typing import Dict, List, Tuple, Union
import uuid

import concurrent.futures as futures
import grpc
from google.protobuf.message import Message

from toybox_msgs.core.Topic_pb2 import (
    AdvertiseRequest,
    TopicDefinition,
    Confirmation,
    SubscriptionResponse,
    TopicList
)
from toybox_msgs.core.Topic_pb2_grpc import (
    TopicServicer, 
    TopicStub,
    add_TopicServicer_to_server
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
        advertiser_id: str = request.client_id
        advertiser_host: str = request.host
        advertiser_port: int = request.topic_port
        topic_name: str = request.topic_def.topic_name
        message_type: str = request.topic_def.message_type

        conf: Confirmation = Confirmation()
        conf.uuid = "-"
        conf.return_code = 0
        conf.status = ""

        # Check if this topic already exists
        topic: Topic | None = self._topics.get(topic_name, None)
        if topic is not None:
            # The topic already exists, meaning it's either been advertised by a Publisher,
            # or been subscribed to by a Subscriber.
            
            # TODO: I think I'd rather not allow two topics to share a name at all. But we'll see...
            # Don't allow a publisher to re-declare a topic it's already declared.
            if advertiser_id in topic.publishers.keys():
                conf.return_code = 1
                conf.status = f"multiple advertise for topic <{topic_name}> by publisher <{advertiser_id}>"
            # Don't allow two topics to share a name, but not a type
            elif topic.message_type != message_type:
                conf.return_code = 2
                conf.status = f"declared message type <{message_type}> \
                    doesn't match previously advertised <{topic.message_type}"
            else:
                topic.publishers[advertiser_id] = (advertiser_host, advertiser_port)
                conf.status = f"Topic <{topic_name}> advertised successfully."
                print(topic.publishers)
                print('-----------------------------')
                print(topic.subscribers)
                print('-----------------------------')
                print(self._clients)
                # print(f"AAAAAAAAAAAAAAAAAAAAAAAAAAA {[self._clients[x] for x in topic.subscribers]}")

        else:

            self._topics[topic_name] = Topic(
                name=topic_name,
                message_type=message_type,
                publishers={advertiser_id: (advertiser_host, advertiser_port)})
            conf.status = f"Topic <{topic_name}> from client <{advertiser_id}> advertised successfully."
        
        return conf
    
    def DeAdvertiseTopic(self, request, context) -> Confirmation:
        raise NotImplementedError
    
    def SubscribeTopic(
        self, 
        request: TopicDefinition, 
        context: grpc.ServicerContext,
    ) -> SubscriptionResponse:
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
        response: SubscriptionResponse = SubscriptionResponse()
        response.conf.uuid = uuid
        response.conf.return_code = 0
        response.topic_def.CopyFrom(request)

        topic: Topic | None = self._topics.get(topic_name, None) 
        if topic is None:
            # The topic hasn't been advertised by any publishers, or subscribed to
            # by any other subscribers.
            self._topics[topic_name] = Topic(
                name=topic_name,
                message_type=message_type,
                subscribers=[uuid])
        else:
            topic.subscribers.append(uuid)

            for publisher in topic.publishers.keys():
                
                publisher_info: Union[Tuple[str,int],None] = topic.publishers.get(publisher, None)
                if publisher_info is None:
                    raise Exception("something's wrong here") 
                
                response.publisher_list.add(
                    publisher_id=publisher,
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


class TopicServer():

    def __init__(self) -> None:

        self._topics: Dict[str, Topic] = {}
        self._servicer: TopicRPCServicer = TopicRPCServicer(topics=self._topics)

        self.not_started: bool = True

    def serve(self) -> None:
        
        self._server: grpc.Server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_TopicServicer_to_server(
            self._servicer, 
            self._server
        )

        self._server.add_insecure_port('[::]:50051')
        
        self._server.start()
        self.not_started = False



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
    advertise_req.client_id = client_name
    advertise_req.host = client_host
    advertise_req.topic_port = topic_port
    advertise_req.topic_def.uuid = str(uuid.uuid4())
    advertise_req.topic_def.topic_name = topic_name
    advertise_req.topic_def.message_type = message_type.DESCRIPTOR.full_name

    conf: Confirmation = stub.AdvertiseTopic(request=advertise_req)
    return (conf.return_code == 0)

def subscribe_topic_rpc(
    topic_name: str,
    message_type: str,
) -> List[Tuple[str,str,int]]:

    subscribe_req: TopicDefinition = TopicDefinition(
        uuid=str(uuid.uuid4()),
        topic_name=topic_name,
        message_type=message_type,
    )
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