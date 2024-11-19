#!/usr/bin/env python3

from dataclasses import dataclass
import time
from typing import Any, Callable, cast, Dict, List, Tuple, Union 

from toybox_sim.entities import Entity
from toybox_sim.plugins.plugins import Plugin, PLUGIN_TYPE, BaseControlPluginIF
from toybox_sim.plugins.DiffDrivePlugin import DiffDrivePlugin
from toybox_sim.gui import SimWindow
import toybox_sim.file_parse


class World:

    def __init__(
        self, 
        name: str = "default",
        entities: Dict[str,Entity] = {},
        window: SimWindow | None = None
    ) -> None:
        
        self._name: str = name
        self._entities: Dict[str, Entity] = entities
        self._time: float = 0.0
        self._loop_frequency: int = 60
        
        # handle GUI if present
        self._window: SimWindow | None = window
        self._USE_GUI = True if (self._window is not None) else False
        
        if self._USE_GUI and self.window is not None:
            self.window.load_visuals(self._entities)

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, new_name: str) -> None:
        self._name = new_name

    @property
    def entities(self) -> Dict[str, Entity]:
        return self._entities

    @property
    def USE_GUI(self) -> bool:
        return self._USE_GUI

    @USE_GUI.setter
    def use_gui(self, use_gui: bool) -> None:
        self._USE_GUI = use_gui

    @property
    def window(self) -> SimWindow | None:
        return self._window
    
    @window.setter
    def window(self, window: SimWindow) -> None:
        self._window = window
        self._USE_GUI = True
        
        print("window_setter")
        
        for entity in self.entities:
            print(f"{entity}, {self.entities[entity].plugins}")

        self._window.entities = self._entities
        self._window.load_visuals(self.entities)
        self._window.schedule_loop(self.step, frequency=self._loop_frequency)

    def add_entity(self, entity: Entity) -> bool:
        if entity.id in self._entities.keys():
            print(f'Entity with id <{entity.id}> already in world <{self._name}>')
            return False
        else:
            self._entities[entity.id] = entity
        
        return True

    def run(self) -> None:

        # if we're using GUI, let pyglet handle the loop
        if self._USE_GUI and self.window is not None:
            for entity in self.entities:
                print(f"{entity}, {self.entities[entity].plugins}")
            self.window.run()

        else:
            self.loop()

    def loop(
        self, 
        frequency: int = 1,
        timestep: float = -1
    ) -> None:
        
        loop_period: float = 1 / frequency
        dt: float = timestep if (timestep > 0) else loop_period
        start_time: float = time.time()

        while True:

            self.step(dt)
            
            # "best effort" time sync 
            time_delta: float = time.time() - start_time
            if time_delta < loop_period:
                time.sleep(loop_period - time_delta)
            start_time = time.time() 

    def step(
        self, 
        dt: float = 0.01
    ) -> None:

        # ripe for parallelization
        for entity_id in self._entities:
            
            entity: Entity = self._entities[entity_id]

            # How much this entity will move; default is not moving at all
            position_delta: Tuple[float,float,float] = (0.0,0.0,0.0)

            # If the entity has a BASE_CONTROL plugin, this is how we'll
            # report it's expected position change while respecting the plugins
            # motion model.
            plugin_delta: Tuple[float,float,float] | None = None

            for plugin in entity.plugins.values():
                
                plugin.call()

                if plugin.plugin_type is PLUGIN_TYPE.MOVEMENT:
                    pass
                elif plugin.plugin_type is PLUGIN_TYPE.BASE_CONTROL:
                    # BASE_CONTROL plugins determine their own position deltas
                    # based on internal motion models. We need to "ask" the plugin
                    # what motion will look like based on it's current velocity, pose,
                    # and dt.
                    assert isinstance(plugin, BaseControlPluginIF)

                    # TODO: This should probably go away...
                    if plugin.id == "DiffyDrivington":
                        plugin.set_target_velocity(1, 3.14 / 20)
                    elif plugin.id == "DiffyDrivington2":
                        plugin.set_target_velocity(0, 3.14)

                    vel_target: Tuple[float,float] = plugin.get_target_velocity()
                    plugin_delta = plugin.get_pose_change(
                        velocity=vel_target, # For now, unmodified
                        current_pose=entity.pose,
                        dt=dt)

                elif plugin.plugin_type is PLUGIN_TYPE.INTEROCEPTIVE:
                    pass
                elif plugin.plugin_type is PLUGIN_TYPE.EXTEROCEPTIVE:
                    pass
                else:
                    print(f"Unhandled plugin type: {plugin.plugin_type}")
                

            # If any of the plugins applied a position change, add it to the position_delta
            if plugin_delta is not None:
                position_delta = tuple(sum(x) for x in zip(position_delta, plugin_delta))
            
            entity.pose.update(delta_p=position_delta)

        self._time += dt

def main():
    
    sim_window: SimWindow = SimWindow()

    worldy: World = toybox_sim.file_parse.parse_world_file("/home/wfletcher/toybox/toybox_sim/resources/base_config.json")
    worldy.window = sim_window

    worldy.run()


if __name__ == "__main__":
    main()
