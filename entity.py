#!/usr/bin/env python3

import math

from abc import ABC, abstractmethod
from typing import Tuple, List, Dict

from plugin import Plugin, PluginNotFoundException, DiffDrivePlugin, PLUGIN_TYPE
from primitives import Polygon, Position, Orientation, Pose

class Entity(ABC):

    @property
    @abstractmethod
    def id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def pose(self) -> Pose:
        raise NotImplementedError
    
    @pose.setter 
    def pose(self, pose: Pose) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def shape(self) -> Polygon:
        raise NotImplementedError

    @property
    @abstractmethod
    def plugins(self) -> Dict[str, Plugin]:
        raise NotImplementedError

    @property
    @abstractmethod
    def plugin_types(self) -> Dict[PLUGIN_TYPE, str]:
        raise NotImplementedError

    def load_plugin(self, plugin_id: str, plugin: Plugin) -> bool:

        try:
            if self.get_plugin(plugin_id):
                print("Plugin with ID {plugin_id} already loaded.")
        except PluginNotFoundException:
            self.plugins[plugin_id] = plugin
            self.plugins[plugin_id].initialize(owner=self)
            self.plugin_types[plugin.plugin_type] = plugin_id
            return True

        return False

    def get_plugin(self, plugin_id: str) -> Plugin:
        
        if plugin_id not in self.plugins.keys():
            raise PluginNotFoundException(plugin_id=plugin_id, object_id=self.id)
        else:
            return self.plugins[plugin_id]

class Agent(Entity):

    def __init__(
        self, 
        id: str = "", 
        shape: Polygon = None,
        position: Tuple[float, float] = (0.0,0.0),
        orientation: float = 0.0,
        plugins: Dict[str, Plugin] = {}
    ) -> None:

        self._id: str = id
        self._shape: Polygon = shape if (shape) else Polygon()
        self._position: Position = Position(x=position[0], y=position[1])
        self._orientation: Orientation = Orientation(theta=orientation)
        self._pose: Pose = Pose(position=self._position, orientation=self._orientation)
        self._plugins: Dict[str, Plugin] = plugins
        self._plugin_types: Dict[PLUGIN_TYPE, str] = {}

    # @property
    # def position(self) -> Position:
    #     return self._position

    # @position.setter
    # def position(self, position: Position) -> None:
    #     self._position = position
    
    # @property
    # def orientation(self) -> Orientation:
    #     return self._orientation

    # @orientation.setter
    # def orientation(self, orientation: Orientation) -> None:
    #     self._orientation = orientation

    @property
    def pose(self) -> Pose:
        return self._pose
    
    @pose.setter
    def pose(self, pose: Pose) -> None:
        self._pose = pose

    @property
    def shape(self) -> Polygon:
        return self._shape

    @property
    def id(self) -> str:
        return self._id
    
    @property
    def plugins(self) -> Dict[str, Plugin]:
        return self._plugins

    @property
    def plugin_types(self) -> Dict[PLUGIN_TYPE, str]:
        return self._plugin_types
    
def main() -> None:

    pass

if __name__ == '__main__':
    main()
