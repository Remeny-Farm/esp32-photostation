"""Printable parts. Each module exposes:

  build(p) -> bpy Object   modelled in its assembly frame (see params.py)
  PRINT_ROT                Euler degrees (x, y, z) into the print orientation
  COUNT                    how many to print
  checks(p, ob) -> list    optional part-specific errors, run on the built part
                           before the print rotation
"""

import importlib

PARTS = ["rail", "carriage", "module_body", "module_lid", "board_sled", "window_frame",
         "bowl_holder", "antenna_holder", "cable_clip"]


def load(name):
    return importlib.import_module(f"parts.{name}")
