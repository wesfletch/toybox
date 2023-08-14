from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TopicDefinition(_message.Message):
    __slots__ = ["uuid", "topic_name", "message_type"]
    UUID_FIELD_NUMBER: _ClassVar[int]
    TOPIC_NAME_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    uuid: str
    topic_name: str
    message_type: str
    def __init__(self, uuid: _Optional[str] = ..., topic_name: _Optional[str] = ..., message_type: _Optional[str] = ...) -> None: ...

class SubscriberList(_message.Message):
    __slots__ = ["subscriber_id"]
    SUBSCRIBER_ID_FIELD_NUMBER: _ClassVar[int]
    subscriber_id: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, subscriber_id: _Optional[_Iterable[str]] = ...) -> None: ...

class PublisherList(_message.Message):
    __slots__ = ["publisher_id"]
    PUBLISHER_ID_FIELD_NUMBER: _ClassVar[int]
    publisher_id: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, publisher_id: _Optional[_Iterable[str]] = ...) -> None: ...

class Confirmation(_message.Message):
    __slots__ = ["return_code", "topic", "status", "subscribers", "publishers"]
    RETURN_CODE_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIBERS_FIELD_NUMBER: _ClassVar[int]
    PUBLISHERS_FIELD_NUMBER: _ClassVar[int]
    return_code: int
    topic: TopicDefinition
    status: str
    subscribers: SubscriberList
    publishers: PublisherList
    def __init__(self, return_code: _Optional[int] = ..., topic: _Optional[_Union[TopicDefinition, _Mapping]] = ..., status: _Optional[str] = ..., subscribers: _Optional[_Union[SubscriberList, _Mapping]] = ..., publishers: _Optional[_Union[PublisherList, _Mapping]] = ...) -> None: ...
