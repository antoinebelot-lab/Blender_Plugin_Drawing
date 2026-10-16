# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from . import export, hardsurface, profiles, references, scene, trace

_modules = (scene, references, trace, profiles, hardsurface, export)


def register():
    for module in _modules:
        for cls in module.classes:
            bpy.utils.register_class(cls)


def unregister():
    for module in reversed(_modules):
        for cls in reversed(module.classes):
            bpy.utils.unregister_class(cls)
