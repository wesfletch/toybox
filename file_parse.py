#!/usr/bin/env python3

import json
from io import TextIOWrapper
from pydoc import locate

from entity import Entity, Thing, Agent
from plugin import Plugin
from simulate import World

from typing import Dict, List


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
    json_file: Dict = json.load(json_file)

    return parse_world_json(json_file)

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
    world_name: str = ""
    entities: Dict[str,Entity] = {}

    if "name" in world_json:
        world_name = world_json["name"]

    if "entities" in world_json:
        entities_json: List[str] = world_json["entities"]
        entities = parse_entities(entities_json)

    return World(
        name=world_name,
        entities=entities
    )

def parse_entities(
    entities_json: List[str],
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
    
    entity: Entity

    if "id" not in entity_config.keys():
        raise Exception(f"No 'id' field provided for entity {entity_config}")

    if entity_config["type"] == "agent":
        entity = Agent(id=entity_config["id"])        
    else:
        entity = Thing(id=entity_config["id"])

    if "plugins" in entity_config:
        plugins: Dict[str,Plugin] = parse_plugins(entity_config["plugins"])
        entity.load_plugins(plugins)

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
    
    plugin: Plugin

    plugin_type: str = plugin_json.get("type")
    # uses locate() to get constructor of Plugin sub-class with plugin_type
    plugin_inst: Plugin = locate(f'plugin.{plugin_type}')

    plugin: Plugin = plugin_inst.from_config(plugin_json)

    return plugin


def main():

    json_file: TextIOWrapper = open("base_config.json", "r")
    json_file: Dict = json.load(json_file)
    worldy: World = parse_world_file(json_file)
    print(worldy.entities["test"])

if __name__ == "__main__":
    main()