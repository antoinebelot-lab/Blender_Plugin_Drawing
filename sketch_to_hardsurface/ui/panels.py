# SPDX-License-Identifier: GPL-3.0-or-later
"""Sidebar (N panel) of the 3D viewport, tab "Sketch2HS"."""

import bpy
from bpy.types import Panel

from .. import utils

CATEGORY = "Sketch2HS"


class _S2HPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY


def _toggle_row(layout, role, text):
    op = layout.operator("s2h.toggle_role", text=text, icon='HIDE_OFF')
    op.role = role


class S2H_PT_main(_S2HPanel, Panel):
    bl_label = "Sketch to Hard Surface"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.unit_settings
        row = layout.row(align=True)
        row.operator("s2h.setup_units", icon='DRIVER_DISTANCE')
        if settings.system == 'METRIC' and settings.length_unit == 'MILLIMETERS':
            row.label(text="", icon='CHECKMARK')


class S2H_PT_references(_S2HPanel, Panel):
    bl_label = "1. References"
    bl_parent_id = "S2H_PT_main"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("s2h.add_reference", icon='IMAGE_REFERENCE')
        row.operator("s2h.reference_opacity", text="", icon='MOD_OPACITY')
        _toggle_row(row, 'REFERENCE', "")

        refs = [o for o in context.scene.objects if o.s2h_role == 'REFERENCE' and utils.is_reference(o)]
        if not refs:
            layout.label(text="Load a sketch, a blueprint or a photo", icon='INFO')
            return
        col = layout.column(align=True)
        for obj in refs:
            row = col.row(align=True)
            active = obj == context.active_object
            op = row.operator("s2h.select_object", text=obj.name, emboss=active,
                              icon='RADIOBUT_ON' if active else 'RADIOBUT_OFF')
            op.name = obj.name
            row.prop(obj, "color", index=3, text="", slider=True)
            row.prop(obj, "hide_select", text="", emboss=False)
            row.prop(obj, "hide_viewport", text="", emboss=False)

        ref = context.active_object
        if utils.is_reference(ref):
            box = layout.box()
            width, height = utils.reference_world_size(ref)
            box.label(text="%s x %s" % (utils.format_length(context, width), utils.format_length(context, height)),
                      icon='FIXED_SIZE', translate=False)
            row = box.row(align=True)
            row.operator("s2h.reference_set_width", icon='ARROW_LEFTRIGHT')
            row.operator("s2h.calibrate_reference", icon='DRIVER_DISTANCE')
            box.prop(ref, "empty_image_depth", expand=True)


class S2H_PT_profiles(_S2HPanel, Panel):
    bl_label = "2. Profiles and Volume"
    bl_parent_id = "S2H_PT_main"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("s2h.trace_reference", icon='TRACKER')
        row = layout.row(align=True)
        row.operator("s2h.new_profile", icon='GREASEPENCIL')
        row.operator("s2h.extrude_profile", icon='MOD_SOLIDIFY')
        row = layout.row(align=True)
        row.operator("s2h.build_blockout", icon='MOD_BOOLEAN')
        _toggle_row(row, 'PROFILE', "")
        if context.active_object is not None and context.active_object.s2h_role == 'REFERENCE':
            layout.label(text="Trace the active reference, tune it with F9", icon='INFO')


class S2H_PT_hardsurface(_S2HPanel, Panel):
    bl_label = "3. Hard Surface"
    bl_parent_id = "S2H_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select cutters, then the target (active)")
        grid = layout.grid_flow(columns=2, align=True, even_columns=True)
        for identifier, icon in (("DIFFERENCE", 'SELECT_SUBTRACT'), ("UNION", 'SELECT_EXTEND'),
                                 ("INTERSECT", 'SELECT_INTERSECT'), ("SLICE", 'SELECT_DIFFERENCE')):
            op = grid.operator("s2h.boolean", text=self._label(identifier), icon=icon)
            op.operation = identifier
        row = layout.row(align=True)
        row.prop(context.scene.s2h, "boolean_solver", text="")
        _toggle_row(row, 'CUTTER', "")
        col = layout.column(align=True)
        col.operator("s2h.mirror", icon='MOD_MIRROR')
        col.operator("s2h.finish", icon='MOD_BEVEL')
        col.operator("s2h.apply_shape", icon='CHECKMARK')

    @staticmethod
    def _label(identifier):
        from ..operators.hardsurface import OPERATIONS
        for ident, name, _desc in OPERATIONS:
            if ident == identifier:
                return bpy.app.translations.pgettext_iface(name)
        return identifier


class S2H_PT_export(_S2HPanel, Panel):
    bl_label = "4. Usable Mesh"
    bl_parent_id = "S2H_PT_main"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("s2h.check_mesh", icon='VIEWZOOM')
        row.operator("s2h.make_final", icon='MESH_DATA')
        settings = context.scene.s2h
        obj = context.active_object
        if settings.check_report and obj is not None and obj.name == settings.check_object:
            box = layout.box()
            col = box.column(align=True)
            for line in settings.check_report.split("\n"):
                if line.startswith("! "):
                    col.label(text=line[2:], icon='ERROR', translate=False)
                else:
                    col.label(text=line, translate=False)
        row = layout.row(align=True)
        row.label(text="Export")
        op = row.operator("wm.stl_export", text="STL")
        op.export_selected_objects = True
        op = row.operator("wm.obj_export", text="OBJ")
        op.export_selected_objects = True


classes = (
    S2H_PT_main,
    S2H_PT_references,
    S2H_PT_profiles,
    S2H_PT_hardsurface,
    S2H_PT_export,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
