# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect every user-visible string of the add-on (used by the translation test)."""

import pathlib
import re

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "sketch_to_hardsurface"

# Strings that are not meant to be translated.
IGNORE = {"", "STL", "OBJ", "X", "Y", "Z", "Sketch2HS", "Sketch2HS Role", "%s x %s", "Sketch to Hard Surface"}

_SOURCE_PATTERNS = (
    re.compile(r'rpt\(\s*"((?:[^"\\]|\\.)+)"'),
    re.compile(r'\btext="((?:[^"\\]|\\.)+)"'),
    re.compile(r'\bheading="((?:[^"\\]|\\.)+)"'),
    re.compile(r'\bn_\(\s*"((?:[^"\\]|\\.)+)"'),
)


def _operator_strings(cls):
    import bpy
    out = [cls.bl_label, cls.__doc__.strip()]
    module, name = cls.bl_idname.split(".")
    rna = getattr(getattr(bpy.ops, module), name).get_rna_type()
    for prop in rna.properties:
        if prop.identifier == "rna_type" or prop.is_hidden:
            continue
        out += [prop.name, prop.description]
        if prop.type == 'ENUM' and not prop.is_enum_flag:
            for item in prop.enum_items:
                out += [item.name, item.description]
    return out


def collect(addon):
    """All strings to translate, given the imported (registered) add-on package."""
    import bpy
    from sketch_to_hardsurface import operators, properties, ui
    strings = []
    for module in operators._modules:
        for cls in module.classes:
            strings += _operator_strings(cls)
    for cls in ui.panels.classes:
        strings.append(cls.bl_label)
    for cls in properties.classes:
        strings += [p.name for p in cls.bl_rna.properties if p.identifier not in {"rna_type", "name"}
                    and not p.is_hidden and p.identifier != "boolean_solver"]
        strings += [cls.bl_rna.properties["boolean_solver"].name,
                    cls.bl_rna.properties["boolean_solver"].description]
    role = bpy.types.Object.bl_rna.properties["s2h_role"]
    strings += [role.description] + [i.name for i in role.enum_items] + [i.description for i in role.enum_items]
    for path in PACKAGE.rglob("*.py"):
        if path.name == "translations.py":
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in _SOURCE_PATTERNS:
            strings += [m.encode().decode("unicode_escape") for m in pattern.findall(text)]
    seen, result = set(), []
    for s in strings:
        if s and s not in IGNORE and s not in seen:
            seen.add(s)
            result.append(s)
    return result
