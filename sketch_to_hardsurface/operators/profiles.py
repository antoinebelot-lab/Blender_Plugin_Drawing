# SPDX-License-Identifier: GPL-3.0-or-later
"""Profiles: draw, close/fill, extrude and combine views into a blockout."""

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import Operator
from mathutils import Matrix, Vector

from .. import utils
from ..utils import rpt

_AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))


def _snap_to_axis(vec, tolerance=0.999):
    for axis in _AXES:
        d = vec.dot(axis)
        if abs(d) >= tolerance:
            return axis * (1.0 if d > 0 else -1.0)
    return vec.normalized()


def _plane_normal(points):
    """Normal of the best-fit plane through ``points`` (None if degenerate)."""
    pts = np.array([p[:] for p in points], dtype=np.float64)
    if len(pts) < 3:
        return None
    _u, s, vh = np.linalg.svd(pts - pts.mean(axis=0))
    if s[1] < 1e-9:
        return None  # collinear
    return Vector(vh[2]).normalized()


def _close_open_chains(bm):
    """Join both ends of every open edge chain."""
    done = set()
    for start in [v for v in bm.verts if len(v.link_edges) == 1]:
        if start in done:
            continue
        prev, cur = None, start
        while True:
            done.add(cur)
            nxt = [e.other_vert(cur) for e in cur.link_edges if e.other_vert(cur) is not prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            if len(cur.link_edges) != 2:
                break
        done.add(cur)
        if cur is not start and len(cur.link_edges) == 1 and bm.edges.get((start, cur)) is None:
            bm.edges.new((start, cur))


def fill_profile(obj, normal_hint=None):
    """Make sure ``obj`` (mesh) has faces: close open chains and fill loops.

    Returns True when the mesh ends up with at least one face.
    """
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    try:
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
        if bm.faces:
            return True
        if len(bm.verts) < 3:
            return False
        _close_open_chains(bm)
        normal = _plane_normal([v.co for v in bm.verts])
        if normal is None:
            return False
        if normal_hint is not None and normal.dot(normal_hint) < 0.0:
            normal.negate()
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=True, edges=bm.edges[:], normal=normal)
        if not bm.faces:
            return False
        bm.normal_update()
        for face in bm.faces:
            if face.normal.dot(normal) < 0.0:
                face.normal_flip()
        bm.to_mesh(mesh)
        mesh.update()
        return True
    finally:
        bm.free()


def _profile_size(obj):
    """Largest extent of the base mesh (ignores an existing extrusion)."""
    if not obj.data.vertices:
        return 0.0
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    extent = np.ptp(co.reshape(-1, 3), axis=0) * np.abs(np.array(obj.matrix_world.to_scale()))
    return float(extent.max())


def curve_to_mesh(context, obj):
    """Replace a curve object by a mesh object with the same name and place."""
    depsgraph = context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    name, matrix, collections, role = obj.name, obj.matrix_world.copy(), list(obj.users_collection), obj.s2h_role
    bpy.data.objects.remove(obj)
    new = bpy.data.objects.new(name, mesh)
    new.matrix_world = matrix
    new.s2h_role = role
    for coll in collections:
        coll.objects.link(new)
    return new


class S2H_OT_new_profile(Operator):
    """Start a profile with one vertex at the 3D cursor, then Ctrl+Right-click in an orthographic view to add points"""
    bl_idname = "s2h.new_profile"
    bl_label = "Draw Profile"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        utils.ensure_object_mode(context)
        rv3d = context.space_data.region_3d
        view_normal = rv3d.view_rotation @ Vector((0.0, 0.0, 1.0))
        normal = _snap_to_axis(view_normal)
        mesh = bpy.data.meshes.new("Profile")
        mesh.from_pydata([context.scene.cursor.location.copy()], [], [])
        obj = utils.new_object(context, "Profile", mesh, 'PROFILE')
        obj["s2h_normal"] = list(normal)
        utils.select_only(context, [obj])
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='VERT')
        bpy.ops.mesh.select_all(action='SELECT')
        if rv3d.view_perspective != 'ORTHO' or normal.dot(view_normal) < 0.999:
            self.report({'WARNING'}, rpt("Switch to an orthographic axis view (Numpad 1, 3, 7) to draw flat"))
        else:
            self.report({'INFO'}, rpt("Ctrl+Right-click to add points, then Extrude Profile"))
        return {'FINISHED'}


class S2H_OT_extrude_profile(Operator):
    """Close and fill the selected outlines (meshes or curves) and give them a live thickness"""
    bl_idname = "s2h.extrude_profile"
    bl_label = "Extrude Profile"
    bl_options = {'REGISTER', 'UNDO'}

    depth: FloatProperty(name="Depth", description="Thickness (0: largest size of the profile)",
                         min=0.0, default=0.0, subtype='DISTANCE', unit='LENGTH')
    side: EnumProperty(
        name="Direction",
        items=(
            ("CENTER", "Centered", "Extrude on both sides of the drawing plane"),
            ("FRONT", "Front", "Extrude toward the face normal"),
            ("BACK", "Back", "Extrude away from the face normal"),
        ),
        default='CENTER',
    )
    mirror_x: BoolProperty(name="X", description="Mirror across the YZ plane of the object", default=False)
    mirror_y: BoolProperty(name="Y", description="Mirror across the XZ plane of the object", default=False)
    mirror_z: BoolProperty(name="Z", description="Mirror across the XY plane of the object", default=False)

    @classmethod
    def poll(cls, context):
        return any(o.type in {'MESH', 'CURVE'} for o in context.selected_objects)

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "depth")
        layout.prop(self, "side")
        row = layout.row(align=True, heading="Mirror")
        row.prop(self, "mirror_x", toggle=True)
        row.prop(self, "mirror_y", toggle=True)
        row.prop(self, "mirror_z", toggle=True)

    def execute(self, context):
        utils.ensure_object_mode(context)
        done, failed = [], []
        for obj in [o for o in context.selected_objects if o.type in {'MESH', 'CURVE'}]:
            if obj.type == 'CURVE':
                obj = curve_to_mesh(context, obj)
            hint = Vector(obj["s2h_normal"]) if "s2h_normal" in obj else None
            if not fill_profile(obj, hint):
                failed.append(obj.name)
                continue
            mirror = (self.mirror_x, self.mirror_y, self.mirror_z)
            mod = obj.modifiers.get(utils.MOD_MIRROR)
            if any(mirror):
                if mod is None:
                    mod = obj.modifiers.new(utils.MOD_MIRROR, 'MIRROR')
                mod.use_axis = mirror
                mod.use_bisect_axis = mirror
                mod.use_clip = True
                mod.use_mirror_merge = True
                utils.move_modifier(obj, mod, 0)
            elif mod is not None:
                obj.modifiers.remove(mod)
            depth = self.depth or max(_profile_size(obj), 1e-4)
            offset = {"CENTER": 0.0, "FRONT": 1.0, "BACK": -1.0}[self.side]
            utils.set_extrude(obj, depth, offset)
            if obj.s2h_role == 'NONE':
                obj.s2h_role = 'PROFILE'
            done.append(obj)
        if failed:
            self.report({'WARNING'}, rpt("Not a closed flat outline: %s", ", ".join(failed)))
        if not done:
            return {'CANCELLED'}
        utils.select_only(context, done)
        return {'FINISHED'}


class S2H_OT_build_blockout(Operator):
    """Intersect profiles drawn in different views (front, side, top) into one live volume"""
    bl_idname = "s2h.build_blockout"
    bl_label = "Combine Views"
    bl_options = {'REGISTER', 'UNDO'}

    hide_profiles: BoolProperty(name="Hide Profiles", default=True)

    @classmethod
    def poll(cls, context):
        return len(utils.selected_meshes(context)) >= 2

    def execute(self, context):
        utils.ensure_object_mode(context)
        profiles = utils.selected_meshes(context)
        lo, hi = utils.evaluated_world_bounds(context, profiles)
        size = hi - lo
        if not all(abs(c) < float("inf") for c in size) or max(size) <= 0.0:
            self.report({'ERROR'}, rpt("The selected profiles are empty"))
            return {'CANCELLED'}
        # A box larger than everything, intersected with each profile, gives
        # their common volume while keeping every profile editable.
        center = (lo + hi) * 0.5
        half = [s * 0.75 + max(size) * 0.05 for s in size]
        mesh = bpy.data.meshes.new("Blockout")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.transform(Matrix.Translation(center) @ Matrix.Diagonal((*half, 1.0)))
        bm.to_mesh(mesh)
        bm.free()
        obj = utils.new_object(context, "Blockout", mesh, 'BLOCKOUT')
        solver = context.scene.s2h.solver()
        for profile in profiles:
            utils.add_boolean(obj, profile, 'INTERSECT', solver)
            if self.hide_profiles:
                profile.hide_set(True)
        utils.select_only(context, [obj])
        self.report({'INFO'}, rpt("Blockout built from %d profiles", len(profiles)))
        return {'FINISHED'}


classes = (
    S2H_OT_new_profile,
    S2H_OT_extrude_profile,
    S2H_OT_build_blockout,
)
