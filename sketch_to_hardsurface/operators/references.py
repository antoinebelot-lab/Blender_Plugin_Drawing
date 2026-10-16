# SPDX-License-Identifier: GPL-3.0-or-later
"""Reference images: import, real-world size and calibration."""

import os

import bpy
import gpu
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, StringProperty)
from bpy.types import Operator, OperatorFileListElement
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import intersect_line_plane

from .. import utils
from ..utils import rpt

VIEW_ITEMS = (
    ("FRONT", "Front", "Seen from the front view (Numpad 1)"),
    ("BACK", "Back", "Seen from the back view (Ctrl Numpad 1)"),
    ("RIGHT", "Right", "Seen from the right view (Numpad 3)"),
    ("LEFT", "Left", "Seen from the left view (Ctrl Numpad 3)"),
    ("TOP", "Top", "Seen from the top view (Numpad 7)"),
    ("BOTTOM", "Bottom", "Seen from the bottom view (Ctrl Numpad 7)"),
    ("BOARD", "Inspiration Board", "Free-floating images arranged on a board, visible in every view"),
)


def _board_count(context):
    return sum(1 for o in context.scene.objects
               if o.s2h_role == 'REFERENCE' and o.get("s2h_view") == 'BOARD')


class S2H_OT_add_reference(Operator):
    """Load sketches or inspiration images as references aligned to a view, at real-world size"""
    bl_idname = "s2h.add_reference"
    bl_label = "Add Reference"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    files: CollectionProperty(type=OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    view: EnumProperty(name="View", items=VIEW_ITEMS, default='FRONT')
    width: FloatProperty(
        name="Real Width",
        description="Real-world width covered by the whole image (0: 100 mm, calibrate later)",
        min=0.0, default=0.0, subtype='DISTANCE', unit='LENGTH',
    )
    opacity: FloatProperty(name="Opacity", min=0.0, max=1.0, default=0.5, subtype='FACTOR')
    depth: EnumProperty(
        name="Depth",
        items=(
            ("BACK", "Behind", "Always drawn behind the model"),
            ("DEFAULT", "Default", "Depth tested like any other object"),
            ("FRONT", "In Front", "Always drawn over the model"),
        ),
        default='BACK',
    )
    lock: BoolProperty(name="Lock Selection", description="Make the reference unselectable in the viewport",
                       default=False)

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "view")
        layout.prop(self, "width")
        layout.prop(self, "opacity")
        layout.prop(self, "depth")
        layout.prop(self, "lock")

    def _paths(self):
        paths = [os.path.join(self.directory, f.name) for f in self.files if f.name]
        if not paths and self.filepath:
            paths = [self.filepath]
        return [p for p in paths if os.path.isfile(p)]

    def execute(self, context):
        paths = self._paths()
        if not paths:
            self.report({'ERROR'}, rpt("No image file selected"))
            return {'CANCELLED'}
        if self.view != 'BOARD' and len(paths) > 1:
            self.report({'WARNING'}, rpt("Only the first image is used for an axis view"))
            paths = paths[:1]

        utils.ensure_object_mode(context)
        width = self.width or utils.meters_to_bu(context, 0.1)
        board_index = _board_count(context)
        created = []
        for path in paths:
            try:
                image = bpy.data.images.load(path, check_existing=True)
            except RuntimeError as exc:
                self.report({'ERROR'}, rpt("Cannot load %s: %s", os.path.basename(path), exc))
                continue
            obj = utils.new_object(context, "Ref %s" % os.path.splitext(image.name)[0], None, 'REFERENCE')
            obj.empty_display_type = 'IMAGE'
            obj.data = image
            obj.empty_image_offset = (-0.5, -0.5)
            obj.use_empty_image_alpha = True
            obj.color[3] = self.opacity
            obj.empty_image_depth = self.depth
            obj.hide_render = True
            obj.hide_select = self.lock
            obj["s2h_view"] = self.view
            utils.set_reference_width(obj, width)
            if self.view == 'BOARD':
                col, row = board_index % 4, board_index // 4
                spacing = width * 1.1
                obj.rotation_euler = utils.VIEW_ROTATIONS['FRONT']
                obj.location = (-1.5 * width - col * spacing, 2.0 * width, 0.5 * width - row * spacing)
                obj.empty_image_side = 'DOUBLE_SIDED'
                obj.show_empty_image_perspective = True
                obj.show_empty_image_only_axis_aligned = False
                obj.empty_image_depth = 'DEFAULT'
                board_index += 1
            else:
                obj.rotation_euler = utils.VIEW_ROTATIONS[self.view]
                obj.empty_image_side = 'FRONT'
                obj.show_empty_image_orthographic = True
                obj.show_empty_image_perspective = False
                obj.show_empty_image_only_axis_aligned = True
            created.append(obj)

        if not created:
            return {'CANCELLED'}
        utils.select_only(context, created)
        self.report({'INFO'}, rpt("%d reference(s) added", len(created)))
        return {'FINISHED'}


class S2H_OT_reference_set_width(Operator):
    """Resize the active reference so that the whole image has this real width"""
    bl_idname = "s2h.reference_set_width"
    bl_label = "Set Real Width"
    bl_options = {'REGISTER', 'UNDO'}

    width: FloatProperty(name="Real Width", min=1e-6, default=1.0, subtype='DISTANCE', unit='LENGTH')

    @classmethod
    def poll(cls, context):
        return utils.is_reference(context.active_object)

    def invoke(self, context, _event):
        self.width = utils.reference_world_size(context.active_object)[0]
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        utils.set_reference_width(context.active_object, self.width)
        return {'FINISHED'}


class S2H_OT_reference_opacity(Operator):
    """Set the opacity of every reference image at once"""
    bl_idname = "s2h.reference_opacity"
    bl_label = "Opacity of All References"
    bl_options = {'REGISTER', 'UNDO'}

    opacity: FloatProperty(name="Opacity", min=0.0, max=1.0, default=0.5, subtype='FACTOR')

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_popup(self, _event)

    def execute(self, context):
        for obj in context.scene.objects:
            if obj.s2h_role == 'REFERENCE' and utils.is_reference(obj):
                obj.color[3] = self.opacity
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Calibration: click two points on the image, type their real distance
# ---------------------------------------------------------------------------

def _draw_calibration(op):
    points = list(op.points)
    if op.hover is not None and len(points) < 2:
        points.append(op.hover)
    if not points:
        return
    size = max(utils.reference_world_size(op.ref)) * 0.01
    x_axis, y_axis = op.axes
    coords = []
    for p in points:
        coords += [p - x_axis * size, p + x_axis * size, p - y_axis * size, p + y_axis * size]
    if len(points) == 2:
        coords += points
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": coords})
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE')
    shader.bind()
    shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
    shader.uniform_float("lineWidth", 2.0)
    shader.uniform_float("color", (1.0, 0.55, 0.0, 1.0))
    batch.draw(shader)
    gpu.state.blend_set('NONE')


class S2H_OT_calibrate_reference(Operator):
    """Click two points on the active reference (Shift: horizontal/vertical), then type their real distance"""
    bl_idname = "s2h.calibrate_reference"
    bl_label = "Calibrate Scale"

    _PASS = {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM',
             'NDOF_MOTION', 'NUMPAD_PERIOD', 'NUMPAD_1', 'NUMPAD_3', 'NUMPAD_7', 'NUMPAD_5'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and utils.is_reference(context.active_object))

    def invoke(self, context, _event):
        self.ref = context.active_object
        self.window_region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        self.rv3d = context.area.spaces.active.region_3d
        if self.window_region is None or self.rv3d is None:
            return {'CANCELLED'}
        rot = self.ref.matrix_world.to_3x3().normalized()
        self.axes = (rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0)))
        self.normal = rot @ Vector((0, 0, 1))
        self.points = []
        self.hover = None
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_calibration, (self,), 'WINDOW', 'POST_VIEW')
        context.window_manager.modal_handler_add(self)
        self._header(context)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        if len(self.points) == 0:
            text = rpt("Calibrate: click the first point on the reference  (Esc: cancel)")
        else:
            dist = (self.hover - self.points[0]).length if self.hover is not None else 0.0
            text = rpt("Calibrate: click the second point, Shift: horizontal/vertical  |  %s",
                       utils.format_length(context, dist))
        context.area.header_text_set(text)

    def _plane_point(self, event):
        region = self.window_region
        coord = (event.mouse_x - region.x, event.mouse_y - region.y)
        origin = view3d_utils.region_2d_to_origin_3d(region, self.rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, self.rv3d, coord)
        point = intersect_line_plane(origin, origin + direction, self.ref.matrix_world.translation, self.normal)
        if point is not None and event.shift and self.points:
            start = self.points[0]
            delta = point - start
            dx, dy = delta.dot(self.axes[0]), delta.dot(self.axes[1])
            point = start + (self.axes[0] * dx if abs(dx) >= abs(dy) else self.axes[1] * dy)
        return point

    def _finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.area.header_text_set(None)
        context.area.tag_redraw()

    def modal(self, context, event):
        context.area.tag_redraw()
        if event.type in self._PASS:
            return {'PASS_THROUGH'}
        if event.type in {'MOUSEMOVE', 'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.hover = self._plane_point(event)
            self._header(context)
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            point = self._plane_point(event)
            if point is None:
                return {'RUNNING_MODAL'}
            self.points.append(point)
            if len(self.points) == 2:
                self._finish(context)
                a, b = self.points
                if (b - a).length < 1e-9:
                    self.report({'ERROR'}, rpt("The two points are identical"))
                    return {'CANCELLED'}
                bpy.ops.s2h.calibrate_apply('INVOKE_DEFAULT', point_a=a, point_b=b)
                return {'FINISHED'}
            self._header(context)
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._finish(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class S2H_OT_calibrate_apply(Operator):
    """Scale the active reference so that the measured segment gets its real length"""
    bl_idname = "s2h.calibrate_apply"
    bl_label = "Set Real Distance"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    point_a: FloatVectorProperty(size=3, subtype='XYZ', options={'HIDDEN'})
    point_b: FloatVectorProperty(size=3, subtype='XYZ', options={'HIDDEN'})
    real_length: FloatProperty(name="Real Distance", min=0.0, subtype='DISTANCE', unit='LENGTH')

    @classmethod
    def poll(cls, context):
        return utils.is_reference(context.active_object)

    def _measured(self):
        return (Vector(self.point_b) - Vector(self.point_a)).length

    def invoke(self, context, _event):
        if self.real_length <= 0.0:
            self.real_length = self._measured()
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text=rpt("Measured: %s", utils.format_length(context, self._measured())))
        layout.prop(self, "real_length")

    def execute(self, context):
        measured = self._measured()
        if measured < 1e-9 or self.real_length <= 0.0:
            self.report({'ERROR'}, rpt("Invalid distance"))
            return {'CANCELLED'}
        ref = context.active_object
        factor = self.real_length / measured
        anchor = Vector(self.point_a)
        ref.empty_display_size *= factor
        matrix = ref.matrix_world.copy()
        matrix.translation = anchor + (matrix.translation - anchor) * factor
        ref.matrix_world = matrix
        self.report({'INFO'}, rpt("Reference scaled by %.4f", factor))
        return {'FINISHED'}


classes = (
    S2H_OT_add_reference,
    S2H_OT_reference_set_width,
    S2H_OT_reference_opacity,
    S2H_OT_calibrate_reference,
    S2H_OT_calibrate_apply,
)
