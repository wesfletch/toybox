#!/usr/bin/env python3

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Tuple
import uuid

from typing import TYPE_CHECKING

from toybox_sim.primitives import Pose, Velocity
from toybox_sim.context import PluginContext


class PluginNotFoundException(Exception):
    """Exception raised when a plugin cannot be found. 

    Args:
        plugin_id (str): the name of the plugin that couldn't be found
        object_id (str, optional): The name of the object that was searched for the plugin. Defaults to "".
    """
    def __init__(self, plugin_id: str, object_id: str = ""):
        self.message = f'No plugin \'{plugin_id}\' found for object \'{object_id}\''
        super().__init__(self.message)


class PLUGIN_TYPE(Enum):
    MOVEMENT = 1
    BASE_CONTROL = 2
    INTEROCEPTIVE = 3
    EXTEROCEPTIVE = 4


class Plugin(ABC):

    def __init__(
        self,
        id: str | None = None,
        owner_id: str | None = None,
        context: PluginContext | None = None,
    ) -> None:

        self._id: str = id if (id is not None) else str(uuid.uuid4())
        self._owner_id: str | None = owner_id

        self._context: PluginContext | None = context

    @property
    def id(self) -> str:
        return self._id

    @property
    def owner_id(self) -> str | None:
        return self._owner_id

    @property
    def context(self) -> PluginContext | None:
        return self._context
    
    @context.setter
    def context(self, context: PluginContext) -> None:
        self._context = context

    @property
    @abstractmethod
    def plugin_type(self) -> PLUGIN_TYPE:
        raise NotImplementedError

    @abstractmethod
    def initialize(self, owner_id: str) -> None:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_config(
        cls,
        json_config: Dict[str,str]
    ) -> 'Plugin':
        raise NotImplementedError

    @abstractmethod
    def parse_config(self, json_dict: Dict[str,str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def call(self) -> Any:
        raise NotImplementedError


class BaseControlPluginIF(ABC):

    @abstractmethod
    def get_pose_change(        
        self, 
        velocity: Velocity,
        current_pose: Pose,
        dt: float
    ) -> Tuple[float, float, float]:
        raise NotImplementedError

    @abstractmethod
    def get_target_velocity(
        self
    ) -> Velocity:
        raise NotImplementedError
    
    @abstractmethod
    def set_target_velocity(
        self, 
        *args, 
        **kwargs
    ) -> None:
        raise NotImplementedError
