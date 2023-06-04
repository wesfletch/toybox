#!/usr/bin/env python3

import math

from abc import ABC, abstractmethod
from typing import Any, Tuple, List, Dict, Union

from plugin import Plugin, PluginNotFoundException, DiffDrivePlugin, PLUGIN_TYPE
from primitives import Polygon, Position, Orientation, Pose

class Entity(ABC):

    @abstractmethod
    def __init__(
        self,
        id: str = "",
        shape: Polygon = None,
        pose: Pose = None,
        plugins: Dict[str,Plugin] = {},
        sprite: str = None
    ) -> None:
        
        self._id: str = id
        self._shape: Polygon = shape if (shape) else Polygon()
        self._pose: Pose = pose if (pose is not None) else Pose()
        self._sprite: Union[str,None] = sprite

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
    def sprite(self) -> Union[str,None]:
        return self._sprite
    
    @sprite.setter
    def sprite(self, new_sprite: str) -> None:
        self._sprite = new_sprite

class HasPlugins(ABC):

    def __init__(
        self,
        owner: Entity,
        plugins: Dict[str,Plugin] = {}
    ) -> None:
        self._owner = owner
        self._plugins: Dict[str,Plugin] = plugins

    @property
    def plugins(self) -> Dict[str, Plugin]:
        return self._plugins

    def load_plugins(self, plugins: Dict[str,Plugin]) -> None:
        for plugin in plugins.keys():
            self.load_plugin(plugin_id=plugin, plugin=plugins[plugin])

    def load_plugin(self, plugin_id: str, plugin: Plugin) -> bool:

        try:
            if self.get_plugin(plugin_id):
                print("Plugin with ID {plugin_id} already loaded.")
        except PluginNotFoundException:
            self.plugins[plugin_id] = plugin
            self.plugins[plugin_id].initialize(owner=self._owner)
            return True

        return False

    def get_plugin(self, plugin_id: str) -> Plugin:
        
        if self.plugins is None:
            raise PluginNotFoundException(plugin_id=plugin_id, object_id=self.id)

        if plugin_id not in self.plugins.keys():
            raise PluginNotFoundException(plugin_id=plugin_id, object_id=self._owner.id)
        else:
            return self.plugins[plugin_id]

class Agent(Entity, HasPlugins):

    def __init__(
        self, 
        id: str = "", 
        shape: Polygon = None,
        pose: Pose = None,
        plugins: Dict[str, Plugin] = {},
        sprite: str = None
    ) -> None:

        Entity.__init__(
            self=self,
            id=id,
            shape=shape,
            pose=pose,
            sprite=sprite,
        )

        HasPlugins.__init__(
            self=self,
            owner=self,
            plugins=plugins,
        )

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

def main() -> None:
    pass

if __name__ == '__main__':
    main()
