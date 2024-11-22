#!/usr/bin/env python3

import json
from io import TextIOWrapper
from pydoc import locate

from toybox_sim.entities import Entity
from toybox_sim.plugins.plugins import Plugin
from toybox_sim.world import World

from typing import Any, cast, Dict, List, Tuple


def parse_world_file(
    filename: str
) -> World:
    """
    Given a json filename, calls parse_world_json to return a World object.

    Args:
        filename (str): filename to load

    Returns:
        World: the World object created by parsing the world file
    """
    json_file: TextIOWrapper = open(filename, "r")
    json_file_loaded: Dict = json.load(json_file)

    return parse_world_json(json_file_loaded)

def parse_world_json(
    world_json: Dict
) -> World:
    """
    Parses a json dictionary into a World object

    Args:
        world_json (Dict): json dictionary to parse

    Returns:
        World: World object created by parsing the world file
    """
    world_name: str | None = None
    entities: Dict[str,Entity] | None = None

    if "name" in world_json:
        world_name = world_json["name"]

    if "entities" in world_json:
        entities_json: Dict[str,Any] = world_json["entities"]
        entities = parse_entities(entities_json)

    return World(name=world_name, entities=entities)

def parse_entities(
    entities_json: Dict[str, Any],
) -> List[Entity]:
    """
    Parses a list of json strings, returns a list of Entity objects.

    Args:
        entities_json (List[str]): _description_

    Returns:
        List[Entity]: _description_
    """
    entities: Dict[str,Entity] = {}
    entity_config: Dict[str,str]

    for entity_config in entities_json:
        entity: Entity = parse_entity(entity_config)
        entities[entity.id] = entity
    
    return entities

def parse_entity(
    entity_config: Dict[str,str]
) -> Entity:

    if "id" not in entity_config.keys():
        raise Exception(f"No 'id' field provided for entity {entity_config}")

    entity: Entity = Entity(id=entity_config["id"])

    if "position" in entity_config:
        x: float = float(entity_config["position"]["x"])
        y: float = float(entity_config["position"]["y"])
        z: float = float(entity_config["position"]["z"])
        entity.pose.position.x = x
        entity.pose.position.y = y
        entity.pose.position.z = z
    if "plugins" in entity_config:
        plugins: Dict[str,Plugin] = parse_plugins(entity_config["plugins"])
        entity.load_plugins(plugins)
    if "sprite" in entity_config:
        entity.sprite = entity_config["sprite"]
    if "model" in entity_config:
        entity.model = entity_config["model"]

    return entity

def parse_plugins(
    plugins_json: List[str],
) -> Dict[str,Plugin]:

    plugins: Dict[str,Plugin] = {}
    plugin_config: Dict[str,str]

    for plugin_config in plugins_json:
        plugin: Plugin = parse_plugin(plugin_config)
        plugins[plugin.id] = plugin

    return plugins

def parse_plugin(
    plugin_json: Dict[str,str]
) -> Plugin:
    
    plugin_type: str = plugin_json.get("type")

    # Use locate() to get constructor of Plugin sub-class with plugin_type.
    plugin_inst: Plugin = cast(Plugin, locate(f'toybox_sim.plugins.{plugin_type}.{plugin_type}'))
    plugin: Plugin = plugin_inst.from_config(plugin_json)

    return plugin


def main() -> None:

    json_file: TextIOWrapper = open("base_config.json", "r")
    json_loaded: Dict = json.load(json_file)
    worldy: World = parse_world_json(json_loaded)

if __name__ == "__main__":
    main()
