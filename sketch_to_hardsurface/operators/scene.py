# SPDX-License-Identifier: GPL-3.0-or-later
"""Scene setup and visibility helpers."""

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator

from .. import utils
from ..utils import rpt


class S2H_OT_setup_units(Operator):
    """Work in millimetres: metric units, 1 Blender unit = 1 mm, viewport clipping adapted"""
    bl_idname = "s2h.setup_units"
    bl_label = "Millimetre Scene"
    bl_options = {'REGISTER', 'UNDO'}

    unit_scale: BoolProperty(
        name="1 Unit = 1 mm",
        description="Set the unit scale to 0.001 so that modifier defaults suit small objects",
        default=True,
    )

    def execute(self, context):
        settings = context.scene.unit_settings
        settings.system = 'METRIC'
        settings.length_unit = 'MILLIMETERS'
        if self.unit_scale:
            settings.scale_length = 0.001
        clip_start = utils.meters_to_bu(context, 0.0001)
        clip_end = utils.meters_to_bu(context, 100.0)
        for screen in bpy.data.screens:
            for area in screen.areas:
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.clip_start = clip_start
                        space.clip_end = clip_end
        self.report({'INFO'}, rpt("Scene set to millimetres"))
        return {'FINISHED'}


class S2H_OT_toggle_role(Operator):
    """Show or hide every object with this role"""
    bl_idname = "s2h.toggle_role"
    bl_label = "Show/Hide"
    bl_options = {'REGISTER', 'UNDO'}

    role: EnumProperty(items=utils.ROLE_ITEMS, default='REFERENCE', options={'HIDDEN'})

    def execute(self, context):
        objects = [o for o in context.view_layer.objects if o.s2h_role == self.role]
        if not objects:
            return {'CANCELLED'}
        hide = any(not o.hide_get() for o in objects)
        for obj in objects:
            obj.hide_set(hide)
        return {'FINISHED'}


class S2H_OT_select_object(Operator):
    """Select this object and make it active"""
    bl_idname = "s2h.select_object"
    bl_label = "Select"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    name: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        obj = context.scene.objects.get(self.name)
        if obj is None:
            return {'CANCELLED'}
        utils.ensure_object_mode(context)
        utils.select_only(context, [obj])
        return {'FINISHED'}


classes = (
    S2H_OT_setup_units,
    S2H_OT_toggle_role,
    S2H_OT_select_object,
)
