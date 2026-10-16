# SPDX-License-Identifier: GPL-3.0-or-later
"""Make the result usable: mesh check and clean, modifier-free final copy."""

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty
from bpy.types import Operator
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

from .. import utils
from ..utils import n_, rpt


def mesh_report(bm):
    """Counts of everything that makes a mesh hard to print or export."""
    tris = quads = ngons = 0
    for face in bm.faces:
        n = len(face.verts)
        if n == 3:
            tris += 1
        elif n == 4:
            quads += 1
        else:
            ngons += 1
    report = {
        "faces": len(bm.faces), "tris": tris, "quads": quads, "ngons": ngons,
        "open_edges": [e for e in bm.edges if e.is_boundary],
        "non_manifold": [e for e in bm.edges if not e.is_manifold and not e.is_boundary and not e.is_wire],
        "loose": [v for v in bm.verts if not v.link_faces],
        "flipped": [e for e in bm.edges if e.is_manifold and not e.is_contiguous],
        "degenerate": [f for f in bm.faces if f.calc_area() <= 1e-12],
        "volume": bm.calc_volume(signed=True) if bm.faces else 0.0,
    }
    intersecting = set()
    if bm.faces:
        tree = BVHTree.FromBMesh(bm, epsilon=0.0)
        for pair in tree.overlap(tree):
            intersecting.update(pair)
    report["intersecting"] = intersecting
    report["printable"] = not (report["open_edges"] or report["non_manifold"] or report["flipped"]
                               or intersecting or report["loose"]) and report["volume"] > 0.0
    return report


def report_lines(context, obj, rep, dims):
    lines = [
        rpt("Size: %s x %s x %s", *(utils.format_length(context, d, 'LENGTH') for d in dims)),
        rpt("Faces: %d (%d tris, %d quads, %d n-gons)", rep["faces"], rep["tris"], rep["quads"], rep["ngons"]),
        rpt("Volume: %s", utils.format_length(context, abs(rep["volume"]), 'VOLUME')),
    ]
    issues = (
        ("open_edges", n_("Open edges (holes): %d")),
        ("non_manifold", n_("Edges shared by 3+ faces: %d")),
        ("flipped", n_("Inconsistent normals: %d edges")),
        ("intersecting", n_("Self-intersecting faces: %d")),
        ("loose", n_("Loose vertices: %d")),
        ("degenerate", n_("Zero-area faces: %d")),
    )
    for key, msg in issues:
        if rep[key]:
            lines.append("! " + rpt(msg, len(rep[key])))
    if rep["volume"] < 0.0:
        lines.append("! " + rpt("Normals point inward"))
    if any(abs(s - 1.0) > 1e-6 for s in obj.scale):
        lines.append("! " + rpt("Object scale is not applied"))
    lines.append(rpt("Watertight, ready for 3D printing") if rep["printable"]
                 else rpt("Not watertight: fix the issues above before printing"))
    return lines


def evaluated_bmesh(context, obj, world=True):
    depsgraph = context.evaluated_depsgraph_get()
    bm = bmesh.new()
    bm.from_object(obj, depsgraph)
    if world:
        bm.transform(obj.matrix_world)
    return bm


class S2H_OT_check_mesh(Operator):
    """Check the active object (with its modifiers) for holes, flipped normals and self-intersections"""
    bl_idname = "s2h.check_mesh"
    bl_label = "Check Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        utils.ensure_object_mode(context)
        obj = context.active_object
        bm = evaluated_bmesh(context, obj)
        try:
            rep = mesh_report(bm)
            lo, hi = utils.evaluated_world_bounds(context, [obj])
            lines = report_lines(context, obj, rep, hi - lo)
        finally:
            bm.free()

        # Without modifiers the problems can be selected for edit mode.
        if not obj.modifiers and not rep["printable"]:
            local = bmesh.new()
            local.from_mesh(obj.data)
            for elem in local.verts[:] + local.edges[:] + local.faces[:]:
                elem.select = False
            local_rep = mesh_report(local)
            for key in ("open_edges", "non_manifold", "flipped"):
                for edge in local_rep[key]:
                    edge.select = True
            for vert in local_rep["loose"]:
                vert.select = True
            local.faces.ensure_lookup_table()
            for index in local_rep["intersecting"]:
                local.faces[index].select = True
            local.to_mesh(obj.data)
            local.free()
            lines.append(rpt("Problems are selected: Tab to see them in Edit Mode"))

        settings = context.scene.s2h
        settings.check_object = obj.name
        settings.check_report = "\n".join(lines)
        level = {'INFO'} if rep["printable"] else {'WARNING'}
        self.report(level, lines[-1])
        return {'FINISHED'}


class S2H_OT_make_final(Operator):
    """Create a clean, modifier-free copy of the selected objects, ready for export or 3D printing"""
    bl_idname = "s2h.make_final"
    bl_label = "Make Final Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    clean: BoolProperty(name="Clean Up", description="Merge duplicate vertices, remove loose and degenerate "
                        "geometry, make normals consistent", default=True)
    merge_distance: FloatProperty(name="Merge Distance", description="0: 0.001 mm",
                                  min=0.0, default=0.0, subtype='DISTANCE', unit='LENGTH')
    triangulate: BoolProperty(name="Triangulate", default=False)
    apply_scale: BoolProperty(name="Apply Scale", default=True)
    hide_sources: BoolProperty(name="Hide Sources", default=True)

    @classmethod
    def poll(cls, context):
        return bool(utils.selected_meshes(context))

    def execute(self, context):
        utils.ensure_object_mode(context)
        depsgraph = context.evaluated_depsgraph_get()
        merge = self.merge_distance or utils.meters_to_bu(context, 1e-6)
        created, printable = [], 0
        for obj in utils.selected_meshes(context):
            mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph),
                                                   preserve_all_data_layers=True, depsgraph=depsgraph)
            loc, rot, scale = obj.matrix_world.decompose()
            bm = bmesh.new()
            bm.from_mesh(mesh)
            if self.apply_scale:
                bmesh.ops.scale(bm, vec=scale, verts=bm.verts[:])
            if self.clean:
                bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge)
                bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=merge)
                loose = [v for v in bm.verts if not v.link_faces]
                if loose:
                    bmesh.ops.delete(bm, geom=loose, context='VERTS')
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            if self.triangulate:
                bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
            printable += mesh_report(bm)["printable"]
            bm.to_mesh(mesh)
            bm.free()
            final = utils.new_object(context, "%s Final" % obj.name, mesh, 'FINAL')
            if self.apply_scale:
                final.matrix_world = Matrix.LocRotScale(loc, rot, None)
            else:
                final.matrix_world = obj.matrix_world.copy()
            if self.hide_sources:
                for operand in utils.boolean_operands(obj):
                    operand.hide_set(True)
                obj.hide_set(True)
            created.append(final)
        utils.select_only(context, created)
        self.report({'INFO'}, rpt("%d final mesh(es), %d watertight", len(created), printable))
        return {'FINISHED'}


classes = (
    S2H_OT_check_mesh,
    S2H_OT_make_final,
)
