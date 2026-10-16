# SPDX-License-Identifier: GPL-3.0-or-later
"""Hard-surface modelling: live booleans, symmetry, finishing stack."""

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy.types import Operator

from .. import utils
from ..utils import rpt

OPERATIONS = (
    ("DIFFERENCE", "Cut", "Subtract the selected objects from the active one"),
    ("UNION", "Union", "Merge the selected objects into the active one"),
    ("INTERSECT", "Intersect", "Keep only the volume shared with the selected objects"),
    ("SLICE", "Slice", "Cut the active object and keep each cut-out part as a separate live object"),
)


def prepare_cutter(context, cutter, target):
    cutter.display_type = 'WIRE'
    cutter.hide_render = True
    cutter.s2h_role = 'CUTTER'
    utils.move_to_collection(cutter, utils.role_collection(context, 'CUTTER'))
    if cutter.parent is None:
        matrix = cutter.matrix_world.copy()
        cutter.parent = target
        cutter.matrix_world = matrix


class S2H_OT_boolean(Operator):
    """Use the selected objects as live boolean cutters on the active object"""
    bl_idname = "s2h.boolean"
    bl_label = "Boolean"
    bl_options = {'REGISTER', 'UNDO'}

    operation: EnumProperty(name="Operation", items=OPERATIONS, default='DIFFERENCE')

    @classmethod
    def description(cls, _context, properties):
        for identifier, _name, desc in OPERATIONS:
            if identifier == properties.operation:
                return bpy.app.translations.pgettext_tip(desc)
        return ""

    @classmethod
    def poll(cls, context):
        target = context.active_object
        return (target is not None and target.type == 'MESH'
                and len(utils.selected_meshes(context, exclude=target)) >= 1)

    def execute(self, context):
        utils.ensure_object_mode(context)
        target = context.active_object
        cutters = utils.selected_meshes(context, exclude=target)
        solver = context.scene.s2h.solver()

        pieces = []
        if self.operation == 'SLICE':
            # Each piece shares the mesh and copies the modifier stack of the
            # target, so editing the target updates every piece.
            for cutter in cutters:
                piece = target.copy()
                piece.name = "%s Slice" % target.name
                for coll in target.users_collection:
                    coll.objects.link(piece)
                utils.add_boolean(piece, cutter, 'INTERSECT', solver)
                pieces.append(piece)

        operation = 'DIFFERENCE' if self.operation == 'SLICE' else self.operation
        for cutter in cutters:
            prepare_cutter(context, cutter, target)
            utils.add_boolean(target, cutter, operation, solver)

        utils.select_only(context, cutters)
        self.report({'INFO'}, rpt("%d cutter(s) added to %s", len(cutters), target.name))
        return {'FINISHED'}


class S2H_OT_mirror(Operator):
    """Add a live symmetry to the selected objects"""
    bl_idname = "s2h.mirror"
    bl_label = "Mirror"
    bl_options = {'REGISTER', 'UNDO'}

    axis_x: BoolProperty(name="X", default=True)
    axis_y: BoolProperty(name="Y", default=False)
    axis_z: BoolProperty(name="Z", default=False)
    bisect: BoolProperty(name="Bisect", description="Cut away the geometry on the mirrored side", default=True)
    center: EnumProperty(
        name="Center",
        items=(
            ("WORLD", "World Origin", "Mirror across the world planes"),
            ("OBJECT", "Object Origin", "Mirror across the object's own planes"),
        ),
        default='WORLD',
    )

    @classmethod
    def poll(cls, context):
        return bool(utils.selected_meshes(context))

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        row = layout.row(align=True, heading="Axis")
        row.prop(self, "axis_x", toggle=True)
        row.prop(self, "axis_y", toggle=True)
        row.prop(self, "axis_z", toggle=True)
        layout.prop(self, "bisect")
        layout.prop(self, "center")

    def execute(self, context):
        utils.ensure_object_mode(context)
        axes = (self.axis_x, self.axis_y, self.axis_z)
        if not any(axes):
            self.report({'WARNING'}, rpt("Choose at least one axis"))
            return {'CANCELLED'}
        origin = utils.world_origin_empty(context) if self.center == 'WORLD' else None
        for obj in utils.selected_meshes(context):
            mod = obj.modifiers.get(utils.MOD_MIRROR)
            if mod is None or mod.type != 'MIRROR':
                mod = obj.modifiers.new(utils.MOD_MIRROR, 'MIRROR')
            mod.use_axis = axes
            mod.use_bisect_axis = [a and self.bisect for a in axes]
            mod.use_clip = True
            mod.use_mirror_merge = True
            mod.mirror_object = origin
            utils.move_modifier(obj, mod, 0)
        return {'FINISHED'}


class S2H_OT_finish(Operator):
    """Add the hard-surface finishing stack: Smooth by Angle, then an angle-limited bevel with hardened normals"""
    bl_idname = "s2h.finish"
    bl_label = "Hard-Surface Finish"
    bl_options = {'REGISTER', 'UNDO'}

    angle: FloatProperty(name="Sharp Angle", description="Edges sharper than this get crisp shading and a bevel",
                         min=math.radians(1.0), max=math.radians(180.0), default=math.radians(30.0),
                         subtype='ANGLE')
    bevel: BoolProperty(name="Bevel", default=True)
    width: FloatProperty(name="Width", description="Bevel width (0: 1% of the object size)",
                         min=0.0, default=0.0, subtype='DISTANCE', unit='LENGTH')
    segments: IntProperty(name="Segments", min=1, max=16, default=3)
    profile: FloatProperty(name="Profile", description="0.5 is round, higher is flatter (superellipse)",
                           min=0.0, max=1.0, default=0.5, subtype='FACTOR')
    weighted_normal: BoolProperty(name="Weighted Normals",
                                  description="Add a Weighted Normal modifier (useful for low-poly assets without bevel)",
                                  default=False)

    @classmethod
    def poll(cls, context):
        return bool(utils.selected_meshes(context))

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "angle")
        layout.prop(self, "bevel")
        col = layout.column(align=True)
        col.active = self.bevel
        col.prop(self, "width")
        col.prop(self, "segments")
        col.prop(self, "profile")
        layout.prop(self, "weighted_normal")

    def execute(self, context):
        utils.ensure_object_mode(context)
        for obj in utils.selected_meshes(context):
            smooth = utils.add_smooth_by_angle(obj, self.angle)
            bevel = obj.modifiers.get(utils.MOD_BEVEL)
            if self.bevel:
                if bevel is None or bevel.type != 'BEVEL':
                    bevel = obj.modifiers.new(utils.MOD_BEVEL, 'BEVEL')
                bevel.width = self.width or max(obj.dimensions) * 0.01
                bevel.segments = self.segments
                bevel.profile = self.profile
                bevel.limit_method = 'ANGLE'
                bevel.angle_limit = self.angle
                bevel.harden_normals = True
                bevel.use_clamp_overlap = True
                bevel.miter_outer = 'MITER_ARC'
            elif bevel is not None:
                obj.modifiers.remove(bevel)
                bevel = None
            weighted = obj.modifiers.get(utils.MOD_WEIGHTED)
            if self.weighted_normal:
                if weighted is None or weighted.type != 'WEIGHTED_NORMAL':
                    weighted = obj.modifiers.new(utils.MOD_WEIGHTED, 'WEIGHTED_NORMAL')
                weighted.keep_sharp = True
                weighted.mode = 'FACE_AREA'
            elif weighted is not None:
                obj.modifiers.remove(weighted)
                weighted = None
            # Measured order: Smooth by Angle before Bevel keeps the hardened
            # normals exact; Weighted Normal (optional) goes last.
            utils.pin_in_order(obj, [smooth, bevel, weighted])
        return {'FINISHED'}


class S2H_OT_apply_shape(Operator):
    """Apply mirror, extrusion and booleans into the mesh, keeping the finishing stack live"""
    bl_idname = "s2h.apply_shape"
    bl_label = "Apply Shape"
    bl_options = {'REGISTER', 'UNDO'}

    hide_operands: BoolProperty(name="Hide Cutters", default=True)

    @classmethod
    def poll(cls, context):
        return bool(utils.selected_meshes(context))

    def execute(self, context):
        utils.ensure_object_mode(context)
        for obj in utils.selected_meshes(context):
            shape_mods = [m for m in obj.modifiers if not m.use_pin_to_last]
            if not shape_mods:
                continue
            finish = [m for m in obj.modifiers if m.use_pin_to_last]
            states = [m.show_viewport for m in finish]
            for mod in finish:
                mod.show_viewport = False
            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph),
                                                   preserve_all_data_layers=True, depsgraph=depsgraph)
            for mod, state in zip(finish, states):
                mod.show_viewport = state
            operands = utils.boolean_operands(obj)
            for mod in shape_mods:
                obj.modifiers.remove(mod)
            old = obj.data
            name = old.name
            obj.data = mesh
            if old.users == 0:
                bpy.data.meshes.remove(old)
            mesh.name = name
            if self.hide_operands:
                for operand in operands:
                    operand.hide_set(True)
        return {'FINISHED'}


classes = (
    S2H_OT_boolean,
    S2H_OT_mirror,
    S2H_OT_finish,
    S2H_OT_apply_shape,
)
