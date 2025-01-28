#!/usr/bin/env python3

from abc import ABC


class Launchable(ABC):
    """
    Implementing this interface allows a Python class to be 'launch'ed via the 
    mechanisms in toybox_core.launch.
    """
    
    def pre_launch(self) -> bool:
        """
        Set up before this node is launched. Optional.

        It can be safely assumed that the TBX server and its core resources are available 
        during this phase, but OTHER tbx nodes and the resources they create may or may not be, 
        depending on launch order.

        Guaranteed to be called only before launch() and post_launch().
        """
        return True
        
    def launch(self) -> bool:
        """
        Function called to launch the node. Required.

        At this point, the TBX server and its resources are available and all other nodes have 
        completed their prelaunch() phases.

        Guaranteed to be called only after pre_launch() and before post_launch().
        """
        raise NotImplementedError

    def post_launch(self) -> bool:
        """
        Cleanup called after the launch execution ends. Optional.

        Conceptually, this is for gracefully closing out the TBX resources that this Launchable
        is using (e.g., de-registering topics). For killing this Launchable instance, use self.shutdown().
        
        At this point, assume that none of the resources of the other nodes in the system are
        available, but the TBX server is.

        Guaranteed to be called only after pre_launch() and launch() have completed.
        """
        return True

    def shutdown(self) -> None:
        """
        Kill this Launchable.

        Unlike post_launch(), there is no guarantee on when this will be called. Shutdown
        can be triggered at ANY time (during any launch phase) by either the TBX server 
        or the Launchable itself.

        NOTE: This may be called multiple times, so do your best to make it idempotent (sorry).
        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        if hasattr(self, "_name"):
            return self._name
        else:
            raise NotImplementedError("Need to provide a name property.")
