# SPDX-License-Identifier: GPL-3.0-or-later
"""Small Blender helpers shared by the operators."""

import math

import bpy
from bpy.app.translations import pgettext_rpt
from mathutils import Matrix, Vector

ROOT_COLLECTION = "Sketch2HS"
ROLE_COLLECTIONS = {
    "REFERENCE": "S2H References",
    "PROFILE": "S2H Profiles",
    "MODEL": "S2H Models",
    "CUTTER": "S2H Cutters",
    "FINAL": "S2H Final",
}

ROLE_ITEMS = (
    ("NONE", "None", ""),
    ("REFERENCE", "Reference", "Sketch or inspiration image"),
    ("PROFILE", "Profile", "2D outline extruded into a solid"),
    ("BLOCKOUT", "Blockout", "Volume built from several profiles"),
    ("CUTTER", "Cutter", "Boolean operand"),
    ("FINAL", "Final", "Clean, modifier-free mesh ready for export"),
)

# Euler rotations putting an image empty face-on in each orthographic view.
VIEW_ROTATIONS = {
    "FRONT": (math.pi / 2, 0.0, 0.0),
    "BACK": (math.pi / 2, 0.0, math.pi),
    "RIGHT": (math.pi / 2, 0.0, math.pi / 2),
    "LEFT": (math.pi / 2, 0.0, -math.pi / 2),
    "TOP": (0.0, 0.0, 0.0),
    "BOTTOM": (math.pi, 0.0, 0.0),
}

MOD_MIRROR = "S2H Mirror"
MOD_EXTRUDE = "S2H Extrude"
MOD_BEVEL = "S2H Bevel"
MOD_WEIGHTED = "S2H Weighted Normal"
MOD_SMOOTH = "S2H Smooth by Angle"


def n_(msg):
    """Mark a message for translation; it is translated later by :func:`rpt`."""
    return msg


def rpt(msg, *args):
    """Translate a report message, then format it."""
    msg = pgettext_rpt(msg)
    return msg % args if args else msg


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

def unit_scale(context):
    scale = context.scene.unit_settings.scale_length
    return scale if scale > 0 else 1.0


def meters_to_bu(context, meters):
    """Convert a real-world length to Blender units for the current scene."""
    return meters / unit_scale(context)


def format_length(context, value, category='LENGTH'):
    """Display a length (or volume) given in Blender units with scene units."""
    settings = context.scene.unit_settings
    if settings.system == 'NONE':
        return "%.4g" % value
    power = 3 if category == 'VOLUME' else 1
    return bpy.utils.units.to_string(settings.system, category, value * unit_scale(context) ** power,
                                     precision=4)


# ---------------------------------------------------------------------------
# Collections and objects
# ---------------------------------------------------------------------------

def _child_collection(parent, name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in parent.children and coll != parent:
        parent.children.link(coll)
    return coll


def role_collection(context, role):
    """Return (creating it if needed) the collection used for ``role``."""
    root = _child_collection(context.scene.collection, ROOT_COLLECTION)
    return _child_collection(root, ROLE_COLLECTIONS[role])




def move_to_collection(obj, collection):
    for coll in list(obj.users_collection):
        if coll != collection:
            coll.objects.unlink(obj)
    if obj.name not in collection.objects:
        collection.objects.link(obj)


def new_object(context, name, data, role):
    obj = bpy.data.objects.new(name, data)
    obj.s2h_role = role
    collection_role = {"BLOCKOUT": "MODEL", "NONE": "MODEL"}.get(role, role)
    role_collection(context, collection_role).objects.link(obj)
    return obj


def select_only(context, objects, active=None):
    for obj in context.view_layer.objects:
        # Entries can be None right after an object was removed.
        if obj is not None and obj.select_get():
            obj.select_set(False)
    for obj in objects:
        if obj.name in context.view_layer.objects:
            obj.hide_set(False)
            obj.select_set(True)
    if active is None and objects:
        active = objects[-1]
    if active is not None:
        context.view_layer.objects.active = active


def selected_meshes(context, exclude=None):
    return [o for o in context.selected_objects if o.type == 'MESH' and o != exclude]


def ensure_object_mode(context):
    if context.mode != 'OBJECT' and context.active_object is not None:
        bpy.ops.object.mode_set(mode='OBJECT')


def evaluated_world_bounds(context, objects):
    """World-space (min, max) corners of the evaluated geometry."""
    depsgraph = context.evaluated_depsgraph_get()
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for obj in objects:
        ev = obj.evaluated_get(depsgraph)
        for corner in ev.bound_box:
            p = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi


# ---------------------------------------------------------------------------
# Reference images
# ---------------------------------------------------------------------------

def is_reference(obj):
    return (obj is not None and obj.type == 'EMPTY' and obj.empty_display_type == 'IMAGE'
            and obj.data is not None)


def image_aspect(image):
    """Relative width/height of an image empty, as drawn by Blender."""
    w, h = image.size[:]
    if w == 0 or h == 0:
        w = h = 1
    asp_x, asp_y = image.display_aspect[:]
    if asp_x > asp_y:
        h *= asp_y / asp_x
    elif asp_x < asp_y:
        w *= asp_x / asp_y
    if w > h:
        return 1.0, h / w
    return w / h, 1.0


def reference_uv_matrix(ref):
    """Matrix mapping image UV coordinates ``(u, v, 0)`` to world space."""
    ax, ay = image_aspect(ref.data)
    size = ref.empty_display_size
    ox, oy = ref.empty_image_offset[:]
    local = Matrix.Diagonal((size * ax, size * ay, 1.0, 1.0)) @ Matrix.Translation((ox, oy, 0.0))
    return ref.matrix_world @ local


def reference_world_size(ref):
    """(width, height) of the image empty in world units."""
    ax, ay = image_aspect(ref.data)
    scale = ref.matrix_world.to_scale()
    size = ref.empty_display_size
    return size * ax * abs(scale.x), size * ay * abs(scale.y)


def set_reference_width(ref, width):
    """Resize an image empty so that its image is ``width`` units wide."""
    ax, _ay = image_aspect(ref.data)
    scale_x = abs(ref.matrix_world.to_scale().x) or 1.0
    ref.empty_display_size = width / (ax * scale_x)


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------

def boolean_operands(obj):
    return [m.object for m in obj.modifiers
            if m.type == 'BOOLEAN' and m.operand_type == 'OBJECT' and m.object is not None]


def add_boolean(target, operand, operation, solver):
    mod = target.modifiers.new("S2H %s %s" % (operation.title(), operand.name), 'BOOLEAN')
    mod.operand_type = 'OBJECT'
    mod.object = operand
    mod.operation = operation
    mod.solver = solver
    # Pinned finishing modifiers (bevel...) stay after new booleans automatically.
    return mod


def set_extrude(obj, thickness, offset=0.0):
    """Give a flat profile a live thickness (Solidify, simple mode)."""
    mod = obj.modifiers.get(MOD_EXTRUDE)
    if mod is None or mod.type != 'SOLIDIFY':
        mod = obj.modifiers.new(MOD_EXTRUDE, 'SOLIDIFY')
    mod.solidify_mode = 'EXTRUDE'
    mod.thickness = thickness
    mod.offset = offset
    mod.use_rim = True
    mod.use_even_offset = False
    return mod


def move_modifier(obj, mod, index):
    current = obj.modifiers.find(mod.name)
    if current != index:
        obj.modifiers.move(current, index)


def smooth_by_angle_group(angle):
    """Geometry Nodes group: all faces smooth, edges sharper than ``angle`` sharp.

    Built here rather than using Blender's "Smooth by Angle" asset, which loads
    asynchronously (it can fail on first use in 4.2) and whose inputs cannot
    be set the same way in every version. The angle is stored in the group,
    one group per angle value.
    """
    name = "S2H Smooth by Angle %.2f" % math.degrees(angle)
    group = bpy.data.node_groups.get(name)
    if group is not None and group.bl_idname == 'GeometryNodeTree':
        return group
    group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes, links = group.nodes, group.links
    node_in = nodes.new("NodeGroupInput")
    node_out = nodes.new("NodeGroupOutput")
    faces = nodes.new("GeometryNodeSetShadeSmooth")
    faces.domain = 'FACE'
    faces.inputs[2].default_value = True
    edges = nodes.new("GeometryNodeSetShadeSmooth")
    edges.domain = 'EDGE'
    edges.inputs[2].default_value = False
    edge_angle = nodes.new("GeometryNodeInputMeshEdgeAngle")
    compare = nodes.new("FunctionNodeCompare")
    compare.data_type = 'FLOAT'
    compare.operation = 'GREATER_THAN'
    compare.inputs[1].default_value = angle
    # Socket names differ between versions ("Geometry"/"Mesh"): link by index.
    links.new(node_in.outputs[0], faces.inputs[0])
    links.new(faces.outputs[0], edges.inputs[0])
    links.new(edge_angle.outputs[0], compare.inputs[0])
    links.new(compare.outputs[0], edges.inputs[1])
    links.new(edges.outputs[0], node_out.inputs[0])
    for node, (x, y) in ((node_in, (-400, 0)), (faces, (-200, 0)), (edge_angle, (-400, -200)),
                         (compare, (-200, -200)), (edges, (0, 0)), (node_out, (200, 0))):
        node.location = (x, y)
    return group


def add_smooth_by_angle(obj, angle):
    """Add (or update) the "S2H Smooth by Angle" Geometry Nodes modifier."""
    mod = obj.modifiers.get(MOD_SMOOTH)
    if mod is None or mod.type != 'NODES':
        mod = obj.modifiers.new(MOD_SMOOTH, 'NODES')
    old = mod.node_group
    mod.node_group = smooth_by_angle_group(angle)
    if old is not None and old != mod.node_group and old.users == 0:
        bpy.data.node_groups.remove(old)
    return mod


def pin_in_order(obj, mods):
    """Pin ``mods`` to the end of the stack, keeping the given order."""
    mods = [m for m in mods if m is not None]
    for mod in mods:
        mod.use_pin_to_last = False
    # Pinning moves a modifier right before the already pinned ones.
    for mod in reversed(mods):
        mod.use_pin_to_last = True




def world_origin_empty(context):
    """Hidden empty at the world origin, used as a mirror centre."""
    name = "S2H World Origin"
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != 'EMPTY':
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = 'PLAIN_AXES'
        role_collection(context, "CUTTER").objects.link(obj)
        obj.hide_render = True
    obj.matrix_world = Matrix.Identity(4)
    return obj
