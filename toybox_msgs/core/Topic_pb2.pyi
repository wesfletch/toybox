from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

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

class Confirmation(_message.Message):
    __slots__ = ["return_code", "topic"]
    RETURN_CODE_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    return_code: int
    topic: TopicDefinition
    def __init__(self, return_code: _Optional[int] = ..., topic: _Optional[_Union[TopicDefinition, _Mapping]] = ...) -> None: ...
