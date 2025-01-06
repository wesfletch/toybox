#!/usr/bin/env python3

import time
from typing import Dict, Tuple

from toybox_sim.entity import Entity
from toybox_sim.plugins.plugins import PLUGIN_TYPE, BaseControlPluginIF
from toybox_sim.primitives import Velocity, Vector3D, Pose


class World:

    def __init__(
        self, 
        name: str | None = None,
        entities: Dict[str,Entity] | None = None,
    ) -> None:
        
        self._name: str = name if name else "default"
        self._time: float = 0.0
        self._loop_frequency: int = 60

        self._entities: Dict[str, Entity] = entities if entities else {}
        self._shutdown: bool = False

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

    def add_entity(self, entity: Entity) -> bool:
        if entity.id in self._entities.keys():
            print(f'Entity with id <{entity.id}> already in world <{self._name}>')
            return False
        else:
            self._entities[entity.id] = entity
        
        return True

    def loop(
        self, 
        frequency: int = 1,
        timestep: float = -1
    ) -> None:
        
        loop_period: float = 1 / frequency
        dt: float = timestep if (timestep > 0) else loop_period
        start_time: float = time.time()

        while not self._shutdown:

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

                    vel_target: Velocity = plugin.get_target_velocity()
                    vel_current: Velocity = entity.velocity
                    
                    # TODO: here is where I would stick any sort of non-ideal changes to vel, IF I HAD SOME
                    # delta = plugin.get_velocity_change(vel_target, vel_current, anything_else_it_might_need)
                    # entity.velocity.update(delta)
                    entity.velocity = vel_target
                    
                    plugin_delta = plugin.get_pose_change(
                        velocity=entity.velocity, # For now, unmodified
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

    def trigger_shutdown(self) -> None:
        self._shutdown = True