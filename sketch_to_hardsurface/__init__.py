# SPDX-License-Identifier: GPL-3.0-or-later
"""Sketch to Hard Surface: from sketches and inspiration images to clean,
usable hard-surface meshes in Blender.

Workflow: references -> traced or drawn profiles -> volume from several
views -> live booleans and finishing stack -> checked, modifier-free mesh.
"""

# Only read by Blender < 4.2 style "legacy add-on" installs; Blender 4.2+
# uses blender_manifest.toml.
bl_info = {
    "name": "Sketch to Hard Surface",
    "author": "Antoine Belot",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar (N) > Sketch2HS",
    "description": "Turn sketches and references into clean hard-surface meshes",
    "category": "Mesh",
}

from . import operators, properties, translations, ui  # noqa: E402


def register():
    translations.register()
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
    translations.unregister()
