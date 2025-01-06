#!/usr/bin/env python3

from abc import ABC
import atexit
import concurrent.futures
from dataclasses import dataclass, field
from enum import Enum
import importlib.util
from importlib.machinery import ModuleSpec
from importlib.metadata import entry_points, EntryPoints
from inspect import signature, Signature, Parameter
import pathlib
import signal
from types import ModuleType
from typing import Any, Dict, Generic, List, TypeVar, get_args

from toybox_core.Node import Node
from toybox_core.Logging import LOG, TbxLogger


class Launchable(ABC):
    """
    Implementing this interface allows a Python object to be 'launch'ed.
    """
    
    def pre_launch(self) -> bool:
        """
        Set up before this node is launched.
        Optional.
        """
        return True
        
    def launch(self) -> bool:
        """
        Function called to launch the node.
        Required.
        """
        raise NotImplementedError

    def post_launch(self) -> bool:
        """
        Cleanup called after the launch execution ends.
        Optional.
        """
        return True

    def shutdown(self) -> None:
        raise NotImplementedError

    @property
    def name(self) -> Node:
        if hasattr(self, "_name"):
            return self._name
        else:
            raise NotImplementedError("Need to provide a name property.")


T = TypeVar('T')
@dataclass
class NodeParam(Generic[T]):
    name: str
    type: type
    value: T | Parameter.empty = Parameter.empty
    required: bool = True


TBX_NAMESPACE: str = "tbx."
TBX_NODES: str = TBX_NAMESPACE + "nodes"


def discover_all_launchable_nodes() -> Dict[str,Launchable]:

    all_launchable_nodes: Dict[str,Launchable] = {}

    entrypoints: EntryPoints = entry_points(group=TBX_NODES)

    for entry_point in entrypoints:
        package_name: str = entry_point.value.split(".")[0]
        full_name: str = f"{package_name}.{entry_point.name}"
        
        loaded: Any = entry_point.load()

        # Make sure that the node actually subclasses the Launchable
        # interface, so that we can launch() them later
        if issubclass(loaded, Launchable):
            all_launchable_nodes[full_name] = loaded

    return all_launchable_nodes


def discover_one_launchable_node(node_name: str) -> Launchable:

    # TODO: this approach to naming makes it such that all nodes must have unique names,
    # even among different packages, which is probably not what I want...
    launchable_entry: EntryPoints = entry_points().select(group=TBX_NODES, name=node_name)

    # We want exactly one launchable node
    if len(launchable_entry) > 1:
        names: List[str] = [f"{x.name} -> {x.value}" for x in launchable_entry]
        raise Exception(f"Found multiple nodes with name {node_name}: {names}")
    elif len(launchable_entry) < 1:
        raise Exception(f"Found no node with name {node_name}")
    
    launchable_node: Any = launchable_entry[0].load()
    if not issubclass(launchable_node, Launchable):
        raise Exception(f"Found node {node_name}, but it's not a Launchable.")

    return launchable_node


def discover_launchable_node_params(package_name: str, node_name: str) -> Dict[str,NodeParam]:

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
        
        # TODO: This would be a good place for "declared" non-constructor tbx params,
        # like from a @classmethod or something....

    return returned


def get_one_launchable_node_params(node: Launchable) -> Dict[str, NodeParam]:

    params: Dict[str, NodeParam] = {}

    init_func_signature: Signature = signature(node.__init__)
    for param in init_func_signature.parameters.values():
        # We obviously don't care about self here
        if param.name == "self":
            continue

        params[param.name] = NodeParam(
            name=param.name, 
            type=param.annotation,
            required=(param.default is Parameter.empty),
            value=param.default)
        
        # TODO: This would be a good place for "declared" non-constructor tbx params,
        # like from a @classmethod or prelaunch() or something....

    return params


def validate_params(params: Dict[str,NodeParam]) -> bool:
    """
    Ensure that all required (no-default) params are set, and that all
    set params match the expected type.
    """
    for _, param in params.items():
        if param.required and (param.value is Parameter.empty):
            print(f"Failed to provide value for required param <'{param.name}'> with type <'{param.type}'>")
            return False
        elif not isinstance(param.value, param.type):
            print(f"Provided value for param <'{param.name}'> does not match type <'{param.type}'>: {param.value}")
            return False
        
    return True


def unravel_params(params: Dict[str,NodeParam]) -> Dict[str,Any]:

    # TODO: this doesn't work for optionals (e.g., str | None) since None is string-able

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
            # Special handling for None, since None can be cast to str for some reason
            if type(None) in union and param.value is None:
                print(f"{name}, {param.type} == {param.value}")
                value = None

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


class LaunchType(Enum):
    NODE = 1
    LAUNCH_SCRIPT = 2 # TODO
    EXECUTABLE = 3 # TODO


@dataclass
class LaunchDescription():
    name: str
    launch_type: LaunchType = LaunchType.NODE
    launchable_class: Launchable | None = None
    to_launch: Launchable | None = None # TODO: Could this be Launchable | LaunchDescription? Recursive?
    params: Dict[str, NodeParam] = field(default_factory=dict)

    # TODO: unused for now
    priority: int = -1
    group: str = ""

    def set_params(self, params: Dict[str,Any]) -> None:        
        for name, value in params.items():
            param: NodeParam | None = self.params.get(name, None)
            if param is None:
                LOG("WARN", f"Setting param that was not declared by Launchable: {name}")
                param = NodeParam(name=name, type=type(value), value=value, required=False)
                continue
            else:
                param.value = value

        if not validate_params(self.params):
            raise Exception(f"Failed to validate provided parameters.")
        
    def instantiate(self) -> Launchable:
        if self.launchable_class is None:
            raise Exception(f"No Launchable class found, cannot instantiate {self.name}")

        return self.launchable_class(**unravel_params(self.params))


def get_launch_description(
    name: str,
    launch_type: LaunchType = LaunchType.NODE,
) -> LaunchDescription:

    try:
        launchable_node: Launchable = discover_one_launchable_node(node_name=name)
    except Exception as e:
        raise Exception(f"Failed to find node with name `{name}`: {e}")

    description: LaunchDescription = LaunchDescription(
        name=name, 
        launch_type=launch_type,
        launchable_class=launchable_node)
    description.params = get_one_launchable_node_params(launchable_node)

    return description


def load_launch_file(launch_file_path: pathlib.Path) -> ModuleType:

    spec: ModuleSpec | None = importlib.util.spec_from_file_location(name="launch_file", location=launch_file_path)
    if spec is None:
        raise Exception(f"Failed to get spec for launch file {launch_file_path}, for some reason.")
    launch_file: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch_file)

    return launch_file


def get_launch_params_from_file(launch_file_path: pathlib.Path) -> list[NodeParam]:
    
    launch_file: ModuleType = load_launch_file(launch_file_path)

    params: list[NodeParam] = []

    try:
        launch_group: list[LaunchDescription] = launch_file.get_launch_params()
    except AttributeError:
        logger.LOG("DEBUG", f"Launch file {launch_file_path} doesn't implement get_launch_params().")

    return params


def get_launch_descs_from_file(launch_file_path: pathlib.Path, launch_params: list[NodeParam]) -> list[LaunchDescription]:

    # Make sure we have values for any required params in launch_params
    

    launch_file: ModuleType = load_launch_file(launch_file_path)

    # Here's the nasty bit: I've got no way of KNOWING beforehand that the launch file
    # has the function that I need. So I've gotta do the python thing and leap-before-looking.
    try:
        launch_group: list[LaunchDescription] = launch_file.get_launch_descriptions(launch_params=launch_params)
    except AttributeError as e:
        raise Exception(f"Failed to execute get_launch_descriptions() from {launch_file_path}. This function MUST be defined for launch to work properly. Exception was {e}")

    return launch_group


logger: TbxLogger = TbxLogger(name="launch")

class LaunchError(Exception):
    """Failed to launch."""


# TODO: Should separate out pre-, peri-, and post-launch phases, otherwise we can't
# do any of the fancy analysis stuff that we want to do
def launch(to_launch: Launchable | LaunchDescription) -> bool:
    """
    Launch a single Launchable node.
    """

    # Don't try to launch things that aren't Launchables or LaunchDescriptions
    if isinstance(to_launch, LaunchDescription):
        to_launch = to_launch.instantiate()

    if not isinstance(to_launch, Launchable):
        raise LaunchError(f"Object provided as arg `to_launch` isn't a Launchable <{to_launch}>")

    atexit.register(to_launch.shutdown)

    logger.LOG("DEBUG", f"Pre-launch for <{to_launch.name}>")
    pre_result: bool = to_launch.pre_launch()
    if not pre_result:
        logger.LOG("DEBUG", f"Pre-launch for <{to_launch.name}> FAILED.")
        # to_launch.shutdown()
        return False
    
    logger.LOG("DEBUG", f"Launching node <{to_launch.name}>")
    launch_result: bool = to_launch.launch()
    if not launch_result:
        # to_launch.shutdown()
        return False
    
    logger.LOG("DEBUG", f"Post-launch <{to_launch.name}>")
    post_result: bool = to_launch.post_launch()
    if not post_result:
        # to_launch.shutdown()
        return False
    
    logger.LOG("DEBUG", f"Calling shutdown on <{to_launch.name}>")
    to_launch.shutdown()

    return True


def launch_all(launch_descs: List[LaunchDescription]) -> None:
    """
    Launch all provided LaunchDescriptions in parallel.
    Returns when all Launched objects have finished.
    """

    launch_group: List[Launchable] = []
    for desc in launch_descs:
        launch_group.append(desc.instantiate())

    def ctrl_c_handler(signum, frame) -> None:
        for launched in launch_group:
            # launched.node.shutdown_event.set()
            launched.shutdown()
    
    signal.signal(signal.SIGINT, ctrl_c_handler)
    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as exec:

        launch_group_futures: Dict[Launchable,concurrent.futures.Future] = {}
        for launchable in launch_group:
            launch_group_futures[launchable] = exec.submit(launch, launchable)

        concurrent.futures.wait(
            launch_group_futures.values(),
            timeout=None,
            return_when=concurrent.futures.ALL_COMPLETED)
        
    # # TODO: I'd rather use multiprocessing here, but multiprocessing and grpc require extra
    # # work to play nice. Maybe later....
    # l: multiprocessing.Process = multiprocessing.Process(target=launch, args=(listener,))
    # p: multiprocessing.Process = multiprocessing.Process(target=launch, args=(pico_bridge,))
    # for process in [l,p]:
    #     process.start()
    # for process in [l,p]:
    #     process.join()

