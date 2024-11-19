#!/usr/bin/env python3

import toybox_core
from toybox_core import Client as toybox
from toybox_core.Launch import Launchable

launchy: Launchable = Launchable()

toybox.init_node(
    name="testy"
)

print(launchy)