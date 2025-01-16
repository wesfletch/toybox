#!/usr/bin/env python3

from abc import ABC


class Launchable(ABC):
    """
    Implementing this interface allows a Python class to be 'launch'ed.
    """
    
    def pre_launch(self) -> bool:
        """
        Set up before this node is launched. Optional.

        It can be safely assumed that the TBX server and its core resources are available 
        during this phase, but OTHER tbx nodes and the resources they create may or may not be, 
        depending on launch order.

        Guaranteed to be called before launch() and post_launch().
        """
        return True
        
    def launch(self) -> bool:
        """
        Function called to launch the node. Required.

        At this point, the TBX server and its resources are available and other nodes have completed
        their prelaunch phase.

        Guaranteed to be called after pre_launch() and before post_launch().
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
    def name(self) -> str:
        if hasattr(self, "_name"):
            return self._name
        else:
            raise NotImplementedError("Need to provide a name property.")
