#!/usr/bin/env python3

from typing import Dict

from toybox_sim.plugins.plugins import Plugin, PluginNotFoundException
from toybox_sim.primitives import Pose, Velocity


class Entity:

    def __init__(
        self,
        id: str = "",
        pose: Pose | None = None,
        plugins: Dict[str,Plugin] | None = None,
        sprite: str | None = None,
        model: str | None = None,
        velocity: Velocity | None = None,
    ) -> None:
        
        self._id: str = id
        self._plugins: Dict[str,Plugin] = plugins if plugins else {}
        self._sprite: str | None = sprite
        self._model: str | None = model

        self._pose: Pose = pose if (pose is not None) else Pose()
        self._velocity: Velocity = velocity if velocity else Velocity()

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
    def velocity(self) -> Velocity:
        return self._velocity

    @velocity.setter
    def velocity(self, new_vel: Velocity) -> None:
        self._velocity = new_vel

    @property
    def sprite(self) -> str | None:
        return self._sprite
    
    @sprite.setter
    def sprite(self, new_sprite: str) -> None:
        self._sprite = new_sprite

    @property
    def model(self) -> str | None:
        return self._model
    
    @model.setter
    def model(self, new_model: str) -> None:
        self._model = new_model
    
    @property
    def plugins(self) -> Dict[str, Plugin]:
        return self._plugins
    
    def load_plugins(self, plugins: Dict[str,Plugin]) -> None:
        for plugin in plugins.keys():
            self.load_plugin(plugin_id=plugin, plugin=plugins[plugin])
            print(self.plugins)

    def load_plugin(self, plugin_id: str, plugin: Plugin) -> bool:

        try:
            if self.get_plugin(plugin_id):
                print("Plugin with ID {plugin_id} already loaded.")
        except PluginNotFoundException:
            self.plugins[plugin_id] = plugin
            self.plugins[plugin_id].initialize(owner_id=self.id)
            return True

        return False

    def get_plugin(self, plugin_id: str) -> Plugin:
        
        if self.plugins is None or plugin_id not in self.plugins.keys():
            raise PluginNotFoundException(plugin_id=plugin_id, object_id=self.id)
        else:
            return self.plugins[plugin_id]
