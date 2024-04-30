#!/usr/bin/env python3
from abc import ABC
import time
from typing import Dict, List, Union, Tuple, Callable

import toybox_core as tbx
# from toybox_core import init_node
from toybox_core.Connection import Publisher, Subscriber
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

    @property
    def node(self) -> Node:
        if hasattr(self, "_node"):
            return self._node
        else:
            raise NotImplementedError("You're not using the default name for node ('_node'), so you must explicitly define node property.")

    @node.setter
    def node(self, node) -> None:
        self._node = node

logger: TbxLogger = TbxLogger(name="launch")

class LaunchError(Exception):
    """Failed to launch."""

def launch(to_launch: Launchable) -> bool:

    # don't try to launch things that aren't Launchables
    if not isinstance(to_launch, Launchable):
        raise LaunchError(f"Object provided as arg `to_launch` isn't a Launchable <{to_launch}>")
    
    # don't bother trying to launch anything that doesn't have
    # an associated Toybox Node
    if not hasattr(to_launch, "node"):
        raise LaunchError(f"No 'node' member of Launchable <{to_launch}>. Cannot launch.")

    logger.LOG("DEBUG", f"Pre-launch for <{to_launch.node}>")
    pre_result: bool = to_launch.pre_launch()
    if not pre_result:
        return False
    
    logger.LOG("DEBUG", f"Launch for <{to_launch.node}>")
    launch_result: bool = to_launch.launch()
    if not launch_result:
        return False
    
    logger.LOG("DEBUG", f"Post-launch <{to_launch.node}>")
    post_result: bool = to_launch.post_launch()
    if not post_result:
        return False
    
    logger.LOG("DEBUG", f"Calling shutdown on <{to_launch.node}>")
    to_launch.node.shutdown()

    return True

