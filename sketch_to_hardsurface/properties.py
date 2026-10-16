# SPDX-License-Identifier: GPL-3.0-or-later
"""Registered properties: per-object role and per-scene settings."""

import bpy
from bpy.props import EnumProperty, PointerProperty, StringProperty
from bpy.types import PropertyGroup

from .utils import ROLE_ITEMS

_solver_items_cache = []


def _solver_items(_self, _context):
    # Identifiers changed across versions (FAST -> FLOAT, MANIFOLD added in 4.5).
    if not _solver_items_cache:
        prop = bpy.types.BooleanModifier.bl_rna.properties["solver"]
        items = [(e.identifier, e.name, e.description) for e in prop.enum_items]
        # EXACT first so that it is the default (index 0).
        items.sort(key=lambda item: item[0] != "EXACT")
        _solver_items_cache.extend(items)
    return _solver_items_cache


class S2H_SceneSettings(PropertyGroup):
    boolean_solver: EnumProperty(
        name="Boolean Solver",
        description="Solver used by the boolean modifiers this add-on creates",
        items=_solver_items,
    )
    check_object: StringProperty(options={'HIDDEN'})
    check_report: StringProperty(options={'HIDDEN'})

    def solver(self):
        """Selected solver identifier, defaulting to EXACT."""
        return self.boolean_solver or "EXACT"


classes = (S2H_SceneSettings,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.s2h = PointerProperty(type=S2H_SceneSettings)
    bpy.types.Object.s2h_role = EnumProperty(
        name="Sketch2HS Role",
        description="What this object is used for in the sketch to hard surface workflow",
        items=ROLE_ITEMS,
        default="NONE",
    )


def unregister():
    del bpy.types.Object.s2h_role
    del bpy.types.Scene.s2h
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
