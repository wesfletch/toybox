#!/usr/bin/env python3

import unittest

import importlib
from typing import List

MSG_PKGS: List[str] = [
    "core",
    "primitive",
    "state"
]

"""
Admittedly, this is stupid. But I'm really, really tired of accidentally
breaking imports by shuffling things around. So here we are.
"""
class Test_Imports(unittest.TestCase):

    def test_imports(self) -> None:
        for msg_pkg in MSG_PKGS:
            i = importlib.util.find_spec(f"toybox_msgs.{msg_pkg}")

            self.assertTrue(i is not None)