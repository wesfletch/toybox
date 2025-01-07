#!/usr/bin/env python3

from abc import ABC

from toybox_core.Node import Node

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
