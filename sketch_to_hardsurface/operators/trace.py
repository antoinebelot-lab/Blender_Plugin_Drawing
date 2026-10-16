# SPDX-License-Identifier: GPL-3.0-or-later
"""Trace a reference image into profile meshes."""

import math
import time

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy.types import Operator
from mathutils import Vector

from .. import utils
from ..core import image_trace
from ..utils import rpt


def read_pixels(image, max_size):
    """RGBA pixels of ``image`` as an (H, W, 4) array, longest side <= max_size."""
    width, height = image.size[:]
    if width == 0 or height == 0:
        raise RuntimeError(rpt("Image %s has no pixel data (missing file?)", image.name))
    scale = min(1.0, max_size / float(max(width, height)))
    source, temp = image, None
    if scale < 1.0:
        # Let Blender resample a temporary copy: much lighter than reading
        # the full-resolution buffer into Python.
        temp = image.copy()
        temp.scale(max(1, round(width * scale)), max(1, round(height * scale)))
        source = temp
    try:
        w, h = source.size[:]
        buf = np.empty(w * h * 4, dtype=np.float32)
        source.pixels.foreach_get(buf)
    finally:
        if temp is not None:
            bpy.data.images.remove(temp)
    return buf.reshape(h, w, 4)


def build_shapes(bm, shapes, matrix, normal):
    """Add filled faces for ``shapes`` (UV space) to ``bm``."""
    for shape in shapes:
        outer_verts = None
        edges = []
        for loop in [shape.outer] + list(shape.holes):
            verts = [bm.verts.new(matrix @ Vector((u, v, 0.0))) for u, v in loop]
            if outer_verts is None:
                outer_verts = verts
            edges += [bm.edges.new((verts[i - 1], verts[i])) for i in range(len(verts))]
        if shape.holes:
            bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=True, edges=edges, normal=normal)
        else:
            bm.faces.new(outer_verts)
    bm.normal_update()
    for face in bm.faces:
        if face.normal.dot(normal) < 0.0:
            face.normal_flip()


class S2H_OT_trace_reference(Operator):
    """Vectorise the active reference image into clean profiles (tune it in the Adjust Last Operation panel)"""
    bl_idname = "s2h.trace_reference"
    bl_label = "Trace Reference"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Shape",
        items=(
            ("SILHOUETTE", "Silhouette", "Outer outline of the drawing, everything inside is filled"),
            ("REGIONS", "Enclosed Regions", "One shape per area enclosed by lines (panels, separate parts)"),
            ("FILLED", "Inked Areas", "The inked areas themselves, holes kept (silhouettes, solid fills)"),
        ),
        default='SILHOUETTE',
    )
    source: EnumProperty(
        name="Ink",
        items=(
            ("DARK", "Dark on Light", "Pencil or marker on paper"),
            ("LIGHT", "Light on Dark", "Light lines on a dark background"),
            ("ALPHA", "Opaque on Transparent", "Uses the alpha channel (PNG cut-outs)"),
        ),
        default='DARK',
    )
    threshold: FloatProperty(name="Threshold", description="Ink detection level", min=0.01, max=0.99,
                             default=0.5, subtype='FACTOR')
    resolution: IntProperty(name="Resolution", description="Working resolution (longest side, in pixels)",
                            min=64, max=4096, default=1024, subtype='PIXEL')
    gap: IntProperty(name="Close Gaps", description="Bridge gaps in the lines up to about twice this size",
                     min=0, max=32, default=2, subtype='PIXEL')
    thin: IntProperty(name="Remove Thin Parts",
                      description="Remove parts narrower than about twice this size (construction lines "
                      "overshooting the corners)",
                      min=0, max=32, default=2, subtype='PIXEL')
    simplify: FloatProperty(name="Simplify", description="Maximum deviation from the drawing",
                            min=0.0, max=20.0, default=2.0, subtype='PIXEL')
    straighten: FloatProperty(name="Straighten", description="Snap edges within this angle of horizontal or vertical",
                              min=0.0, max=math.radians(20.0), default=math.radians(4.0), subtype='ANGLE')
    min_area: FloatProperty(name="Ignore Smaller Than", description="Ignore specks smaller than this part of the image",
                            min=0.0, max=10.0, default=0.05, subtype='PERCENTAGE')
    keep_holes: BoolProperty(name="Keep Holes", default=True)
    separate: BoolProperty(name="Separate Objects", description="One object per shape", default=False)
    extrude: BoolProperty(name="Extrude", description="Give the profile a live thickness", default=True)
    depth: FloatProperty(name="Depth", description="Extrusion depth (0: as wide as the reference)",
                         min=0.0, default=0.0, subtype='DISTANCE', unit='LENGTH')

    @classmethod
    def poll(cls, context):
        return utils.is_reference(context.active_object)

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "mode")
        layout.prop(self, "source")
        layout.prop(self, "threshold")
        col = layout.column(align=True)
        col.prop(self, "resolution")
        col.prop(self, "gap")
        col.prop(self, "thin")
        col.prop(self, "simplify")
        col.prop(self, "straighten")
        col.prop(self, "min_area")
        layout.prop(self, "keep_holes")
        layout.prop(self, "separate")
        layout.prop(self, "extrude")
        row = layout.row()
        row.active = self.extrude
        row.prop(self, "depth")

    def execute(self, context):
        ref = context.active_object
        start = time.perf_counter()
        try:
            rgba = read_pixels(ref.data, self.resolution)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        shapes = image_trace.trace_image(
            rgba, source=self.source, threshold=self.threshold, mode=self.mode,
            max_size=self.resolution, gap=self.gap, thin=self.thin, simplify=self.simplify,
            min_area=self.min_area / 100.0, straighten_deg=math.degrees(self.straighten),
            keep_holes=self.keep_holes,
        )
        if not shapes:
            # FINISHED (not CANCELLED) keeps the redo panel open for tuning.
            self.report({'WARNING'}, rpt("No shape found: adjust Ink, Threshold or Shape"))
            return {'FINISHED'}

        matrix = utils.reference_uv_matrix(ref)
        normal = (matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        depth = self.depth or max(utils.reference_world_size(ref))
        base_name = ref.name[4:] if ref.name.startswith("Ref ") else ref.name
        groups = [[s] for s in shapes] if self.separate else [shapes]

        created = []
        for group in groups:
            name = "%s Profile" % base_name
            mesh = bpy.data.meshes.new(name)
            bm = bmesh.new()
            build_shapes(bm, group, matrix, normal)
            bm.to_mesh(mesh)
            bm.free()
            obj = utils.new_object(context, name, mesh, 'PROFILE')
            obj["s2h_normal"] = list(normal)
            if self.extrude:
                utils.set_extrude(obj, depth)
            created.append(obj)

        utils.select_only(context, created)
        self.report({'INFO'}, rpt("%d shape(s) traced in %.2f s", len(shapes), time.perf_counter() - start))
        return {'FINISHED'}


classes = (S2H_OT_trace_reference,)
