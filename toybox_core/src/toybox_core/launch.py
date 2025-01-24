#!/usr/bin/env python3

import atexit
import concurrent.futures
from dataclasses import dataclass, field
from enum import Enum
import importlib.util
from importlib.machinery import ModuleSpec
from importlib.metadata import entry_points, EntryPoints
from inspect import signature, Signature, Parameter
import pathlib
import random
import signal
import threading
from types import ModuleType
from typing import Any, Callable, Dict, Generic, List, TypeVar, get_args
from toybox_core.rpc.health import try_health_check_rpc
from typing_extensions import Self

from toybox_core.launchable import Launchable
from toybox_core.logging import LOG, TbxLogger
from toybox_core.metadata import ToyboxMetadata, find_tbx_packages


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

    launchable_params: Dict[str,NodeParam] = {}

    full_node_name: str = f"{package_name}.{node_name}"
    
    all_launchable_nodes: Dict[str,Launchable] = discover_all_launchable_nodes()
    
    node: Launchable | None = all_launchable_nodes.get(full_node_name, None)
    if node is not None:
        init_func_signature: Signature = signature(node.__init__)
        for param in init_func_signature.parameters.values():
            # We obviously don't care about self here
            if param.name == "self":
                continue

            launchable_params[param.name] = NodeParam(
                name=param.name, 
                type=param.annotation,
                required=(param.default is Parameter.empty),
                value=param.default)
        
        # TODO: This would be a good place for "declared" non-constructor tbx params,
        # like from a @classmethod or something....

    return launchable_params


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
    Ensure that all required (no-default-provided) params are set, and that all
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
            # This type is a union.
            # Special handling for None, since None can be cast to str for some reason
            if type(None) in union and param.value is None:
                value = None
            else:
                # Try to cast to each member of the Union until one of them works.
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
    GROUP = 2 # TODO
    EXECUTABLE = 3 # TODO


class LaunchDescription():
    # TODO: unused for now
    priority: int = -1
    group: str = ""

    def __init__(
        self,
        name: str,
        launch_type: LaunchType = LaunchType.NODE,
        params: dict[str,NodeParam] | None = None
    ) -> None:
        
        self.name: str = name
        self.launch_type: LaunchType = launch_type
        self.params: dict[str,NodeParam] = params if params else {}

        # self.launchable_class: Launchable | None = launchable_class

        self._to_launch: list[Launchable] | list[LaunchDescription] | None = None

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

    @property
    def to_launch(
        self,
    ) -> list[Launchable] | list[Self] | None:
        return self._to_launch
    
    @to_launch.setter
    def to_launch(
        self, 
        to_launch: list[Launchable] | list[Self],
    ) -> None:
        assert isinstance(to_launch, list), "It's gotta be a list, brother"
        self._to_launch = to_launch

    def instantiate(self) -> list[Launchable]:

        if self.to_launch is None:
            raise Exception(f"LaunchDescription {self.name} has no 'to_launch' assigned.")

        launchables: list[Launchable] = []

        for launch in self.to_launch:
            # TODO: There's something funky going on with imports from entrypoints that causes
            # isinstance(launch, Launchable) to fail when it shouldn't. After
            # a few hours of debugging, we're just gonna use this dirty hack for now.
            if hasattr(launch, "__bases__") and Launchable in launch.__bases__:
                # TODO: I'm providing ALL params of the parent to the launchable here,
                # could I just provide the needed subset (maybe as a optional param to this function)
                # when I call instantiate on the nested LaunchDescription?
                launchables.append(launch(**unravel_params(self.params))) # type: ignore
            elif isinstance(launch, LaunchDescription):
                # Danger! Recursive...
                sub_launchables: list[Launchable] = launch.instantiate()
                launchables.extend(sub_launchables)
            else:
                raise Exception(f"Something is very wrong... {self.to_launch}")

        return launchables


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
        launch_type=launch_type)
    description.to_launch = [launchable_node]
    description.params = get_one_launchable_node_params(launchable_node)

    return description


def find_launch_file(package: str, launch_file_name: str) -> pathlib.Path:

    tbx_pkgs: dict[str,ToyboxMetadata] = find_tbx_packages()

    meta: ToyboxMetadata | None = tbx_pkgs.get(package, None)
    if meta is None:
        raise Exception(f"Failed to find toybox package with name `{package}`")
    
    return meta.get_launch_file(launch_file_name=launch_file_name)


def load_launch_file(launch_file_path: pathlib.Path) -> ModuleType:

    spec: ModuleSpec | None = importlib.util.spec_from_file_location(name="launch_file", location=launch_file_path)
    if spec is None:
        raise Exception(f"Failed to get spec for launch file {launch_file_path}, for some reason.")
    launch_file: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch_file)

    return launch_file


def get_launch_params_from_file(launch_file_path: pathlib.Path) -> dict[str,NodeParam]:
    
    launch_file: ModuleType = load_launch_file(launch_file_path)

    params: list[NodeParam] | None = None

    # Here's the nasty bit: I've got no way of KNOWING beforehand that the launch file
    # has the function that I need. So I've gotta do the python thing and leap-before-looking.
    try:
        params = launch_file.get_launch_params()
        if params is None:
            logger.LOG("WARN", f"get_launch_params() defined, but no params... Did you remember to return them?")
    except AttributeError:
        logger.LOG("DEBUG", f"Launch file {launch_file_path} doesn't implement get_launch_params().")

    if params is None:
        return {}
    
    # To make things easier for the writer of the launch file, we're returning a list of NodeParams
    # from get_launch_params(). For our purposes, we'll transform that into a dict.
    param_dict: dict[str,NodeParam] = {}
    for param in params:
        if param.name in param_dict:
            raise Exception(f"Duplicate param defined in get_launch_params(): {param.name}")
        param_dict[param.name] = param

    return param_dict


def get_launch_descs_from_file(launch_file_path: pathlib.Path, launch_params: dict[str,NodeParam]) -> LaunchDescription:

    # Make sure we have values for any required params in launch_params
    if not validate_params(launch_params):
        raise Exception(f"Failed to validate input params to launch file {launch_file_path}")

    launch_file: ModuleType = load_launch_file(launch_file_path)

    launch_group: LaunchDescription
    # Here's the nasty bit: I've got no way of KNOWING beforehand that the launch file
    # has the function that I need. So I've gotta do the python thing and leap-before-looking.
    try:
        launch_desc: list[LaunchDescription] | LaunchDescription 
        launch_desc = launch_file.get_launch_descriptions(launch_params=launch_params)
        # For some reason, I've decided to allow two return types from get_launch_descriptions(), 
        # so we have to handle them separately here.
        if isinstance(launch_desc, list):
            launch_group = LaunchDescription(
                name=str(launch_file_path.stem),
                launch_type=LaunchType.GROUP)
            launch_group.to_launch = [x for x in launch_desc]
        elif isinstance(launch_desc, LaunchDescription):
            launch_group = launch_desc
        else:
            raise Exception(f"Invalid return from {launch_file}.get_launch_descriptions(): {launch_desc}")

    except AttributeError as e:
        raise Exception(f"Failed to execute get_launch_descriptions() from {launch_file_path}. This function MUST be defined for launch to work properly. Exception was {e}")

    return launch_group


logger: TbxLogger = TbxLogger(name="launch")

class LaunchError(Exception):
    """Failed to launch."""


# TODO: Should separate out pre-, peri-, and post-launch phases, otherwise we can't
# do any of the fancy analysis stuff that we want to do
def launch(to_launch: Launchable) -> bool:
    """
    Launch a single Launchable node.
    """
    # # Don't try to launch things that aren't Launchables or LaunchDescriptions
    # if isinstance(to_launch, LaunchDescription):
    #     to_launch = to_launch.instantiate()

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

def phase_prelaunch(launchable: Launchable) -> bool:

    if not isinstance(launchable, Launchable):
        raise LaunchError(f"Object provided as arg `launchable` isn't a Launchable <{launchable}>")

    atexit.register(launchable.shutdown)

    logger.LOG("DEBUG", f"Launch phase <PRELAUNCH> for <{launchable.name}>")
    pre_result: bool = launchable.pre_launch()
    if not pre_result:
        logger.LOG("DEBUG", f"Launch phase <PRELAUNCH> for <{launchable.name}> FAILED.")
        return False
    
    return True
    
def phase_launch(launchable: Launchable) -> bool:

    if not isinstance(launchable, Launchable):
        raise LaunchError(f"Object provided as arg `launchable` isn't a Launchable <{launchable}>")

    atexit.register(launchable.shutdown)

    logger.LOG("DEBUG", f"Launch phase <LAUNCH> <{launchable.name}>")
    result: bool = launchable.launch()
    if not result:
        logger.LOG("DEBUG", f"Launch phase <LAUNCH> for <{launchable.name}> FAILED.")
        return False
    
    return True

def phase_postlaunch(launchable: Launchable) -> bool:

    if not isinstance(launchable, Launchable):
        raise LaunchError(f"Object provided as arg `launchable` isn't a Launchable <{launchable}>")

    atexit.register(launchable.shutdown)

    logger.LOG("DEBUG", f"Launch phase <POSTLAUNCH> for <{launchable.name}>")
    result: bool = launchable.post_launch()
    if not result:
        logger.LOG("DEBUG", f"Launch phase <POSTLAUNCH> for <{launchable.name}> FAILED.")
        return False
    
    return True

def launch_phase(launchables: list[Launchable], func: Callable[[Launchable],bool]) -> bool:

    def ctrl_c_handler(signum, frame) -> None:
        for launchable in launchables:
            launchable.shutdown()
    
    signal.signal(signal.SIGINT, ctrl_c_handler)
    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as exec:

        launch_group_futures: dict[Launchable,concurrent.futures.Future] = {}
        for launchable in launchables:
            launch_group_futures[launchable] = exec.submit(func, launchable)

        done, not_done = concurrent.futures.wait(
            launch_group_futures.values(),
            timeout=None,
            return_when=concurrent.futures.ALL_COMPLETED)
        
        for finished_task in done:
            if not finished_task.result:
                return False

    return True


def launch_phase_by_phase(launchables: list[Launchable]) -> None:

    LOG("INFO", f"Starting <PRELAUNCH> phase.")
    if not launch_phase(launchables, phase_prelaunch):
        return False
    LOG("INFO", f"Finished <PRELAUNCH> phase.")

    LOG("INFO", f"Starting <LAUNCH> phase.")
    if not launch_phase(launchables, phase_launch):
        return False
    LOG("INFO", f"Finished <LAUNCH> phase.")

    LOG("INFO", f"Starting <POSTLAUNCH> phase.")
    if not launch_phase(launchables, phase_postlaunch):
        return False
    LOG("INFO", f"Finished <POSTLAUNCH> phase.")


def launch_tbx_server() -> tuple[Launchable,threading.Thread]:

    tbx_server: Launchable = get_launch_description("ToyboxServer").instantiate()[0]

    if not tbx_server.pre_launch():
        tbx_server.shutdown(notify_clients=False)
        raise Exception("Failed to pre-launch the tbx-server")
    
    tbx_server_thread = threading.Thread(target=phase_launch, args=[tbx_server])
    tbx_server_thread.name = "tbx_server"
    tbx_server_thread.start()

    return (tbx_server, tbx_server_thread) 

def launch_all(launch_desc: LaunchDescription, no_server: bool = False, random_launch_order: bool = True) -> None:
    """
    Launch all provided LaunchDescriptions in parallel.
    Returns when all Launched objects have finished.
    """

    if launch_desc.to_launch is None:
        raise Exception("Nothing to launch!")

    # Resolve any LaunchDescriptions within our top-level LaunchDescription
    # and get a set of Launchables.
    launchables: list[Launchable] = launch_desc.instantiate()
    
    # DEBUG: does ordering change the behavior here?
    if random_launch_order:
        random.shuffle(launchables)

    # If we don't have an instance of tbx-server running, add it here.
    tbx_server: Launchable | None = None
    server_thread: threading.Thread | None = None
    if not try_health_check_rpc() and not no_server:
        tbx_server, server_thread = launch_tbx_server()

    # Actually begin the launch process for our launchables.
    launch_phase_by_phase(launchables=launchables)

    # If we inserted a tbx-server, we "need" to kill it when we're done.
    if tbx_server is not None:
        tbx_server.shutdown()
        server_thread.join()

