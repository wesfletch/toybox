#!/usr/bin/env python3

import math

from abc import ABC, abstractmethod
from typing import Tuple, List, Dict

from plugin import Plugin, PluginNotFoundException, DiffDrivePlugin, PLUGIN_TYPE
from primitives import Polygon, Position, Orientation, Pose

class Entity(ABC):

    @abstractmethod
    def __init__(
        self,
        id: str = "",
        shape: Polygon = None,
        pose: Pose = None,
        plugins: Dict[str,Plugin] = {}
    ) -> None:
        
        self._id: str = id
        self._shape: Polygon = shape if (shape) else Polygon()
        self._pose: Pose = pose if pose is not None else Pose()
        self._plugins: Dict[str,Plugin] = plugins

    @property
    def id(self) -> str:
        return self._id

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
    def plugins(self) -> Dict[str, Plugin]:
        return self._plugins

    # @property
    # @abstractmethod
    # def plugin_types(self) -> Dict[PLUGIN_TYPE, str]:
        
    #     raise NotImplementedError

    def load_plugins(self, plugins: Dict[str,Plugin]) -> None:
        for plugin in plugins.keys():
            self.load_plugin(plugin_id=plugin, plugin=plugins[plugin])

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

class Thing(Entity):

    def __init__(
        self,
        id: str = "",
        shape: Polygon = None,
        pose: Pose = None,
    ) -> None:

        super().__init__(
            id=id,
            shape=shape,
            pose=pose,
            plugins=None
        )
        print(self._pose)

class Agent(Entity):

    def __init__(
        self, 
        id: str = "", 
        shape: Polygon = None,
        pose: Pose = None,
        plugins: Dict[str, Plugin] = {}
    ) -> None:

        super().__init__(
            id=id,
            shape=shape,
            pose=pose,
            plugins=None
        )
        
        self._plugin_types: Dict[PLUGIN_TYPE, str] = {}
        for plugin in self._plugins.values():
            self._plugin_types[plugin.id] = plugin.plugin_type

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

    thing: Thing = Thing()

if __name__ == '__main__':
    main()
