#!/usr/bin/env python3

from dataclasses import dataclass
from importlib.metadata import entry_points, EntryPoints
from inspect import signature, Signature, Parameter
from typing import Any, Dict, Generic, Iterable, List, TypeVar, get_args, Union

from toybox_core.Launch import launch, Launchable, LaunchError

TBX_NAMESPACE: str = "tbx."
TBX_NODES: str = TBX_NAMESPACE + "nodes"


T = TypeVar('T')
@dataclass
class NodeParam(Generic[T]):
    name: str
    type: type
    value: T | Parameter.empty = Parameter.empty
    required: bool = True


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

def get_launchable_node_params(package_name: str, node_name: str) -> Dict[str,NodeParam]:

    returned: Dict[str,NodeParam] = {}

    full_node_name: str = f"{package_name}.{node_name}"
    
    all_launchable_nodes: Dict[str,Launchable] = discover_all_launchable_nodes()
    
    node: Launchable | None = all_launchable_nodes.get(full_node_name, None)
    if node is not None:
        init_func_signature: Signature = signature(node.__init__)
        for param in init_func_signature.parameters.values():
            # We obviously don't care about self here
            if param.name == "self":
                continue

            returned[param.name] = NodeParam(
                name=param.name, 
                type=param.annotation,
                required=(param.default is Parameter.empty),
                value=param.default)
        
        # TODO: This would be a good place for "declared" non-constructor params,
        # like from a @classmethod or something....

    return returned

def validate_params(params: Dict[str,NodeParam]) -> bool:

    for name, param in params.items():
        if param.required and param.value is Parameter.empty:
            print(f"Failed to provide value for required param <'{param.name}'> with type <'{param.type}'>")
            return False
        elif not isinstance(param.value, param.type):
            print(f"Provided value for param <'{param.name}'> does not match type <'{param.type}'>: {param.value}")
            return False
        
    return True

def unravel_params(params: Dict[str,NodeParam]) -> Dict[str,Any]:

    returned: Dict[str,Any] = {}

    # Attempt to cast each param value to the correct type
    for name, param in params.items():
        
        value: Any | Parameter.empty = Parameter.empty

        # Handling unions: if the type is not a Union, union will be None
        union: tuple[Any,...] = get_args(param.type)
        if not union:
            # The type isn't a Union. Attempt to cast directly to the type.
            try:
                value = param.type(param.value)
            except (TypeError,ValueError):
                print(f"Failed to cast value <'{param.value}'> to type <'{param.type}'>")
        else:
            # This type is a Union, try to cast to each member of the Union until one of them works.
            for type_in_union in union:
                try:
                    value = type_in_union(param.value)
                    break
                except (TypeError,ValueError):
                    continue

        if value is not Parameter.empty:
            returned[param.name] = value
        else:
            print(f"Failed to cast value <'{param.value}'> to type <'{param.type}'>")

    return returned

def main() -> None:

    nodes = discover_all_launchable_nodes()
    params: Dict[str,NodeParam] = get_launchable_node_params(package_name="toybox_examples", node_name="Listener")
    params["name"].value = "test"
    print(params)
    
    if not validate_params(params):
        return

    listener = nodes["toybox_examples.Listener"](**unravel_params(params))
    launch(to_launch=listener)

if __name__ == "__main__":
    main()