#!/usr/bin/env python3

import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable

# import server
import client

@dataclass
class Topic():
    name: str
    message_type: client.Message 
    publishers: List[client.Client] = field(default_factory=list)
    subscribers: List[client.Client] = field(default_factory=list)

