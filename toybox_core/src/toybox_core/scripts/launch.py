#!/usr/bin/env python3

from dataclasses import dataclass
from importlib.metadata import entry_points, EntryPoints
from inspect import signature, Signature
from typing import Any, Dict, Generic, List, TypeAlias, TypeVar

from toybox_core.Launch import launch, Launchable

TBX_NAMESPACE: str = "tbx."
TBX_NODES: str = TBX_NAMESPACE + "nodes"

# PARAM: TypeAlias = tuple[str, type]

T = TypeVar('T')
@dataclass
class Param(Generic[T]):
    name: str
    type: type
    value: T | None = None


def discover_all_launchable_nodes() -> Dict[str,Launchable]:

    all_launchable_nodes: Dict[str,Launchable] = {}

    entrypoints: EntryPoints = entry_points(group=TBX_NODES)

    for entry_point in entrypoints:
        package_name: str = entry_point.value.split(".")[0]
        full_name: str = f"{package_name}.{entry_point.name}"
        
        loaded: Any = entry_point.load()

        # Make sure that the node actually subclasses the Launchable
        # interface, so that we can actually "launch()" them later
        if issubclass(loaded, Launchable):
            all_launchable_nodes[full_name] = loaded

    return all_launchable_nodes

def get_launchable_node_params(package_name: str, node_name: str) -> List[Param]:

    returned: List[Param] = []

    full_node_name: str = f"{package_name}.{node_name}"
    
    all_launchable_nodes: Dict[str,Launchable] = discover_all_launchable_nodes()
    
    node: Launchable | None = all_launchable_nodes.get(full_node_name, None)
    if node is not None:
        init_func_signature: Signature = signature(node.__init__)
        for param in init_func_signature.parameters.values():
            # We obviously don't care about self here
            if param.name == "self":
                continue

            returned.append(Param(name=param.name, type=param.annotation))

    return returned

def param_list_to_mapping(params: List[Param]) -> Dict[str,Any]:

    returned: Dict = {}

    for param in params:
        returned[param.name] = param.type(param.value)

    return returned

def main() -> None:

    # from toybox_examples.src.toybox_examples.pico_bridge import PicoBridge
    # pico_bridge: PicoBridge = PicoBridge(name="pico_bridge")

    # launch(to_launch=pico_bridge)
    nodes = discover_all_launchable_nodes()
    params: List[Param] = get_launchable_node_params(package_name="toybox_examples", node_name="Listener")

    for param in params:
        if param.name == "name":
            param.value = "test"

    listener = nodes["toybox_examples.Listener"](**param_list_to_mapping(params))
    launch(to_launch=listener)



if __name__ == "__main__":
    main()