#!/usr/bin/env python3

from typing import TYPE_CHECKING

from toybox_sim.primitives import Pose, Velocity
if TYPE_CHECKING:
    from toybox_sim.world import World
    from toybox_sim.gui import SimWindow

class PluginContext:
    """
    The PluginContext defines the interface between Plugin objects and the "World"
    that they operate in.

    The PluginContext should be initialized with the World it will access,
    then the PluginContext can be "attached" to the plugin(s).
    """

    def __init__(self, world: "World") -> None:
        self._world = world
    
    def get_entity_pose(self, entity_name: str) -> Pose | None:
        if entity_name not in self._world._entities.keys():
            return None
        return self._world._entities[entity_name].pose
    
    def get_entity_velocity(self, entity_name: str) -> Velocity | None:
        if entity_name not in self._world._entities.keys():
            return None
        return self._world._entities[entity_name].velocity
    
class WindowContext:

    def __init__(self, window: "SimWindow") -> None:
        self._window: "SimWindow" = window

    def get_window_width(self) -> int:
        return self._window.width
    
    def get_window_height(self) -> int:
        return self._window.height
    
    def get_window_grid_coords(self, x: int, y: int) -> tuple[int,int]:
        return self._window.get_grid_coordinates(x=x, y=y)

    def get_window_pixels_per_meter(self) -> int:
        return self._window.pixels_per_meter