#!/usr/bin/env python3

from abc import ABC

class Client(ABC):
    pass

# may not be needed, can I just use Client for both?
class Subscriber(Client):
    pass
class Publisher(Client):
    pass

class Message():
    """"
    wraps a protobuf class
    """
    pass
