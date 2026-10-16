# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end tests inside Blender, using the ``bpy`` module from PyPI.

    pip install bpy pytest   # bpy needs the Python version Blender ships with
    pytest tests

Skipped automatically when ``bpy`` is not importable.
"""

import math
import pathlib
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import bmesh  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "tests"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


# -- helpers ----------------------------------------------------------------

def save_png(path, ink):
    """Black ink on white paper; ``ink`` rows go top to bottom like a picture."""
    h, w = ink.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[ink, :3] = 0.0
    img = bpy.data.images.new(path.stem, w, h, alpha=True)
    img.pixels.foreach_set(rgba[::-1].ravel())  # Blender stores the bottom row first
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return str(path)


def outline(h, w, box, width=4):
    """Rectangle outline; box = (top, left, bottom, right) in pixels."""
    t, l, b, r = box
    ink = np.zeros((h, w), dtype=bool)
    ink[t:b, l:l + width] = ink[t:b, r - width:r] = True
    ink[t:t + width, l:r] = ink[b - width:b, l:r] = True
    return ink


def select(objects, active):
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active


def evaluated_bm(obj):
    bm = bmesh.new()
    bm.from_object(obj, bpy.context.evaluated_depsgraph_get())
    bm.transform(obj.matrix_world)
    return bm


def world_bounds(obj):
    bm = evaluated_bm(obj)
    co = np.array([v.co[:] for v in bm.verts])
    bm.free()
    return co.min(axis=0), co.max(axis=0)


def volume(obj):
    bm = evaluated_bm(obj)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return vol


# -- fixture ----------------------------------------------------------------

@pytest.fixture(scope="module")
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import sketch_to_hardsurface
    sketch_to_hardsurface.register()
    yield sketch_to_hardsurface
    sketch_to_hardsurface.unregister()


@pytest.fixture
def scene(addon):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    bpy.ops.s2h.setup_units()
    return bpy.context.scene


# -- tests ------------------------------------------------------------------

def test_setup_units(scene):
    assert scene.unit_settings.length_unit == 'MILLIMETERS'
    assert scene.unit_settings.scale_length == pytest.approx(0.001)


def test_reference_placement_and_size(scene, tmp_path):
    path = save_png(tmp_path / "front.png", outline(100, 200, (20, 40, 80, 160)))
    assert bpy.ops.s2h.add_reference(filepath=path, view='FRONT', width=200.0) == {'FINISHED'}
    ref = bpy.context.active_object
    assert ref.s2h_role == 'REFERENCE' and ref.empty_display_type == 'IMAGE'
    from sketch_to_hardsurface import utils
    w, h = utils.reference_world_size(ref)
    assert (w, h) == (pytest.approx(200.0), pytest.approx(100.0))
    # Front view: image plane is XZ, facing -Y.
    normal = ref.matrix_world.to_3x3() @ __import__("mathutils").Vector((0, 0, 1))
    assert normal.y == pytest.approx(-1.0)


def test_trace_front_and_side_then_blockout(scene, tmp_path):
    # Front: 120 x 60 mm rectangle (1 px = 1 mm), side: 80 x 60 mm.
    front = save_png(tmp_path / "front.png", outline(100, 200, (20, 40, 80, 160)))
    side = save_png(tmp_path / "side.png", outline(100, 200, (20, 60, 80, 140)))
    bpy.ops.s2h.add_reference(filepath=front, view='FRONT', width=200.0)
    ref_front = bpy.context.active_object
    assert bpy.ops.s2h.trace_reference(mode='SILHOUETTE') == {'FINISHED'}
    prof_front = bpy.context.active_object
    assert prof_front.s2h_role == 'PROFILE'
    assert prof_front.modifiers[0].type == 'SOLIDIFY'

    lo, hi = world_bounds(prof_front)
    assert lo[0] == pytest.approx(-60.0, abs=1.0) and hi[0] == pytest.approx(60.0, abs=1.0)
    assert lo[2] == pytest.approx(-30.0, abs=1.0) and hi[2] == pytest.approx(30.0, abs=1.0)
    assert hi[1] - lo[1] == pytest.approx(200.0, abs=0.01)   # auto depth = reference width

    bpy.ops.s2h.add_reference(filepath=side, view='RIGHT', width=200.0)
    bpy.ops.s2h.trace_reference(mode='SILHOUETTE')
    prof_side = bpy.context.active_object
    lo, hi = world_bounds(prof_side)
    assert lo[1] == pytest.approx(-40.0, abs=1.0) and hi[1] == pytest.approx(40.0, abs=1.0)

    select([prof_front, prof_side], prof_side)
    assert bpy.ops.s2h.build_blockout() == {'FINISHED'}
    blockout = bpy.context.active_object
    assert blockout.s2h_role == 'BLOCKOUT'
    assert [m.operation for m in blockout.modifiers] == ['INTERSECT', 'INTERSECT']
    assert prof_front.hide_get() and prof_side.hide_get()
    assert volume(blockout) == pytest.approx(120 * 80 * 60, rel=0.04)
    assert ref_front.name in bpy.data.objects


def test_trace_regions_separate(scene, tmp_path):
    ink = outline(100, 200, (20, 40, 80, 160))
    ink[20:80, 98:102] = True
    path = save_png(tmp_path / "panels.png", ink)
    bpy.ops.s2h.add_reference(filepath=path, view='TOP', width=200.0)
    bpy.ops.s2h.trace_reference(mode='REGIONS', separate=True, extrude=False)
    parts = [o for o in bpy.context.selected_objects if o.s2h_role == 'PROFILE']
    assert len(parts) == 2
    assert all(len(p.data.polygons) == 1 and len(p.data.vertices) == 4 for p in parts)


def test_trace_nothing_found_keeps_redo(scene, tmp_path):
    path = save_png(tmp_path / "blank.png", np.zeros((50, 50), dtype=bool))
    bpy.ops.s2h.add_reference(filepath=path, view='FRONT', width=50.0)
    assert bpy.ops.s2h.trace_reference() == {'FINISHED'}
    assert bpy.context.active_object.s2h_role == 'REFERENCE'


def make_box(name, size, location=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=location, verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def test_extrude_open_half_profile_with_mirror(scene):
    # Half of a 40 x 20 rectangle drawn in the XZ plane, open along x = 0.
    mesh = bpy.data.meshes.new("half")
    verts = [(0, 0, 0), (20, 0, 0), (20, 0, 20), (0, 0, 20)]
    mesh.from_pydata(verts, [(0, 1), (1, 2), (2, 3)], [])
    obj = bpy.data.objects.new("half", mesh)
    bpy.context.scene.collection.objects.link(obj)
    select([obj], obj)
    assert bpy.ops.s2h.extrude_profile(depth=10.0, mirror_x=True) == {'FINISHED'}
    assert [m.type for m in obj.modifiers] == ['MIRROR', 'SOLIDIFY']
    assert len(obj.data.polygons) == 1
    assert volume(obj) == pytest.approx(40 * 20 * 10, rel=1e-4)


def test_extrude_curve(scene):
    curve = bpy.data.curves.new("c", 'CURVE')
    spline = curve.splines.new('POLY')
    spline.points.add(3)
    for p, co in zip(spline.points, [(0, 0, 0, 1), (10, 0, 0, 1), (10, 10, 0, 1), (0, 10, 0, 1)]):
        p.co = co
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new("curve", curve)
    bpy.context.scene.collection.objects.link(obj)
    select([obj], obj)
    assert bpy.ops.s2h.extrude_profile(depth=5.0) == {'FINISHED'}
    new = bpy.context.active_object
    assert new.type == 'MESH' and new.name == "curve"
    assert abs(volume(new)) == pytest.approx(500.0, rel=1e-4)


def test_boolean_finish_check_final(scene):
    body = make_box("Body", (40, 40, 20))
    cutter = make_box("Hole", (10, 10, 40))
    select([body], body)
    assert bpy.ops.s2h.finish(width=1.0) == {'FINISHED'}
    select([cutter, body], body)
    assert bpy.ops.s2h.boolean(operation='DIFFERENCE') == {'FINISHED'}
    names = [m.name for m in body.modifiers]
    # Booleans go before the pinned finishing stack, Smooth by Angle before Bevel.
    assert body.modifiers[0].type == 'BOOLEAN'
    assert names.index("S2H Bevel") == len(names) - 1
    assert body.modifiers[-2].type == 'NODES'
    assert cutter.s2h_role == 'CUTTER' and cutter.display_type == 'WIRE' and cutter.parent == body
    assert volume(body) < 40 * 40 * 20 - 10 * 10 * 20 + 1.0

    select([body], body)
    assert bpy.ops.s2h.mirror(axis_x=True) == {'FINISHED'}
    assert body.modifiers[0].type == 'MIRROR'

    assert bpy.ops.s2h.check_mesh() == {'FINISHED'}
    report = scene.s2h.check_report
    assert "Watertight" in report and scene.s2h.check_object == body.name

    assert bpy.ops.s2h.make_final() == {'FINISHED'}
    final = bpy.context.active_object
    assert final.s2h_role == 'FINAL' and not final.modifiers
    assert body.hide_get() and cutter.hide_get()
    from sketch_to_hardsurface.operators.export import mesh_report
    bm = bmesh.new()
    bm.from_mesh(final.data)
    rep = mesh_report(bm)
    bm.free()
    assert rep["printable"], rep


def test_check_mesh_finds_hole(scene):
    box = make_box("Open", (10, 10, 10))
    bm = bmesh.new()
    bm.from_mesh(box.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES_ONLY')
    bm.to_mesh(box.data)
    bm.free()
    select([box], box)
    bpy.ops.s2h.check_mesh()
    assert "Open edges (holes): 4" in scene.s2h.check_report
    assert sum(e.select for e in box.data.edges) == 4


def test_slice_creates_live_piece(scene):
    body = make_box("Body", (40, 40, 20))
    cutter = make_box("Cut", (20, 60, 60), location=(20, 0, 0))
    select([cutter, body], body)
    assert bpy.ops.s2h.boolean(operation='SLICE') == {'FINISHED'}
    piece = bpy.data.objects["Body Slice"]
    assert piece.data == body.data
    assert piece.modifiers[-1].operation == 'INTERSECT'
    assert volume(piece) == pytest.approx(10 * 40 * 20, rel=1e-3)
    assert volume(body) == pytest.approx(30 * 40 * 20, rel=1e-3)


def test_apply_shape_keeps_finish(scene):
    body = make_box("Body", (40, 40, 20))
    cutter = make_box("Hole", (10, 10, 40))
    select([cutter, body], body)
    bpy.ops.s2h.boolean(operation='DIFFERENCE')
    select([body], body)
    bpy.ops.s2h.finish()
    assert bpy.ops.s2h.apply_shape() == {'FINISHED'}
    assert all(m.use_pin_to_last for m in body.modifiers)
    assert len(body.data.polygons) > 6
    assert cutter.hide_get()


def test_calibration_math(scene, tmp_path):
    path = save_png(tmp_path / "cal.png", outline(100, 100, (10, 10, 90, 90)))
    bpy.ops.s2h.add_reference(filepath=path, view='TOP', width=100.0)
    ref = bpy.context.active_object
    # A segment measured as 50 units that really is 25: halve everything around point A.
    assert bpy.ops.s2h.calibrate_apply(point_a=(10, 0, 0), point_b=(60, 0, 0), real_length=25.0) == {'FINISHED'}
    from sketch_to_hardsurface import utils
    assert utils.reference_world_size(ref)[0] == pytest.approx(50.0)
    assert ref.matrix_world.translation.x == pytest.approx(5.0)


def test_translations_cover_ui(addon):
    from sketch_to_hardsurface import translations
    import ui_strings
    fr = {msgid for (_ctx, msgid) in translations.translations_dict["fr_FR"]}
    missing = [s for s in ui_strings.collect(addon) if s not in fr]
    assert not missing, missing


# -- UI ---------------------------------------------------------------------

class FakeLayout:
    """Records nothing but checks that every prop/operator used by a panel exists."""

    ICONS = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())

    def __init__(self, errors):
        self.errors = errors
        self.active = True
        self.scale_y = 1.0
        self.use_property_split = False

    def _child(self, *_args, **_kwargs):
        return FakeLayout(self.errors)

    row = column = box = grid_flow = split = _child

    def _check_icon(self, kwargs):
        icon = kwargs.get("icon")
        if icon is not None and icon not in self.ICONS:
            self.errors.append("unknown icon %s" % icon)

    def label(self, **kwargs):
        self._check_icon(kwargs)

    def separator(self, **_kwargs):
        pass

    def prop(self, data, prop, **kwargs):
        self._check_icon(kwargs)
        if prop not in data.bl_rna.properties:
            self.errors.append("%s has no property %r" % (data, prop))

    def operator(self, idname, **kwargs):
        self._check_icon(kwargs)
        module, name = idname.split(".")
        try:
            props = getattr(getattr(bpy.ops, module), name).get_rna_type().properties
        except (AttributeError, KeyError):
            self.errors.append("unknown operator %s" % idname)
            props = {}
        errors = self.errors

        class Props:
            def __setattr__(self, key, value):
                if key not in props:
                    errors.append("%s has no property %r" % (idname, key))

        return Props()


def test_panels_draw(scene, tmp_path):
    from sketch_to_hardsurface.ui import panels
    assert "MOD_BEVEL" in FakeLayout.ICONS and "NOT_AN_ICON" not in FakeLayout.ICONS
    path = save_png(tmp_path / "ui.png", outline(64, 64, (8, 8, 56, 56)))
    bpy.ops.s2h.add_reference(filepath=path, view='FRONT', width=64.0)
    scene.s2h.check_object = bpy.context.active_object.name
    scene.s2h.check_report = "Size: 1\n! Open edges (holes): 4"
    errors = []
    for cls in panels.classes:
        attrs = {"layout": FakeLayout(errors)}
        if hasattr(cls, "_label"):
            attrs["_label"] = staticmethod(cls._label)
        cls.draw(type("FakePanel", (), attrs)(), bpy.context)
    assert not errors, errors


def test_trace_downscales_large_images(scene, tmp_path):
    path = save_png(tmp_path / "big.png", outline(600, 900, (100, 150, 500, 750), width=12))
    bpy.ops.s2h.add_reference(filepath=path, view='FRONT', width=900.0)
    images_before = len(bpy.data.images)
    assert bpy.ops.s2h.trace_reference(resolution=128, gap=0) == {'FINISHED'}
    assert len(bpy.data.images) == images_before          # temporary copy removed
    lo, hi = world_bounds(bpy.context.active_object)
    assert lo[0] == pytest.approx(-300.0, abs=8.0) and hi[0] == pytest.approx(300.0, abs=8.0)
    assert lo[2] == pytest.approx(-200.0, abs=8.0) and hi[2] == pytest.approx(200.0, abs=8.0)


def test_finish_shading_is_crisp(scene):
    """Large flat faces must shade flat and bevels must blend into them."""
    body = make_box("Body", (40, 40, 20))
    cutter = make_box("Hole", (10, 10, 40), location=(8, 8, 0))
    select([cutter, body], body)
    bpy.ops.s2h.boolean(operation='DIFFERENCE')
    select([body], body)
    assert bpy.ops.s2h.finish(width=1.0, segments=3) == {'FINISHED'}
    assert [m.name for m in body.modifiers][-2:] == ["S2H Smooth by Angle", "S2H Bevel"]
    mesh = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    assert mesh.has_custom_normals
    normals = mesh.corner_normals
    big = [p for p in mesh.polygons if p.area > 50.0]
    assert len(big) >= 6
    worst = min(normals[i].vector.dot(p.normal) for p in big for i in p.loop_indices)
    assert worst > 0.9999
    # Bevel corners touching a big face share its normal (hardened).
    on_big = {}
    for p in big:
        for v in p.vertices:
            on_big[v] = p.normal.copy()
    blend = [normals[i].vector.dot(on_big[mesh.loops[i].vertex_index])
             for p in mesh.polygons if p.area <= 50.0 for i in p.loop_indices
             if mesh.loops[i].vertex_index in on_big]
    assert blend and min(blend) > 0.999
    # Re-running with another angle swaps the node group, no duplicate modifier.
    select([body], body)
    bpy.ops.s2h.finish(angle=math.radians(45))
    assert sum(m.type == 'NODES' for m in body.modifiers) == 1


def test_extrude_auto_depth_ignores_previous_extrusion(scene):
    mesh = bpy.data.meshes.new("sq")
    mesh.from_pydata([(0, 0, 0), (30, 0, 0), (30, 0, 10), (0, 0, 10)], [(0, 1), (1, 2), (2, 3), (3, 0)], [])
    obj = bpy.data.objects.new("sq", mesh)
    bpy.context.scene.collection.objects.link(obj)
    select([obj], obj)
    assert bpy.ops.s2h.extrude_profile() == {'FINISHED'}
    assert obj.modifiers["S2H Extrude"].thickness == pytest.approx(30.0)
    obj.modifiers["S2H Extrude"].thickness = 500.0
    bpy.ops.s2h.extrude_profile()
    assert obj.modifiers["S2H Extrude"].thickness == pytest.approx(30.0)


def test_board_multiple_files_and_reference_tools(scene, tmp_path):
    paths = [save_png(tmp_path / ("insp%d.png" % i), outline(40, 60, (5, 5, 35, 55))) for i in range(5)]
    directory = str(tmp_path)
    files = [{"name": pathlib.Path(p).name} for p in paths]
    assert bpy.ops.s2h.add_reference(directory=directory, files=files, view='BOARD', width=60.0) == {'FINISHED'}
    boards = [o for o in bpy.data.objects if o.get("s2h_view") == 'BOARD']
    assert len(boards) == 5
    assert len({tuple(round(c, 3) for c in o.location) for o in boards}) == 5     # laid out on a grid
    assert all(o.show_empty_image_perspective for o in boards)

    select([boards[0]], boards[0])
    assert bpy.ops.s2h.reference_set_width(width=120.0) == {'FINISHED'}
    from sketch_to_hardsurface import utils
    assert utils.reference_world_size(boards[0])[0] == pytest.approx(120.0)

    assert bpy.ops.s2h.reference_opacity(opacity=0.2) == {'FINISHED'}
    assert all(o.color[3] == pytest.approx(0.2) for o in boards)

    assert bpy.ops.s2h.toggle_role(role='REFERENCE') == {'FINISHED'}
    assert all(o.hide_get() for o in boards)
    assert bpy.ops.s2h.toggle_role(role='REFERENCE') == {'FINISHED'}
    assert not any(o.hide_get() for o in boards)

    assert bpy.ops.s2h.select_object(name=boards[3].name) == {'FINISHED'}
    assert bpy.context.active_object == boards[3] and boards[3].select_get()


def test_trace_light_and_alpha_sources(scene, tmp_path):
    h, w = 80, 80
    rgba = np.zeros((h, w, 4), dtype=np.float32)          # transparent background
    rgba[20:60, 20:60] = (1.0, 1.0, 1.0, 1.0)              # opaque white square
    img = bpy.data.images.new("alpha", w, h, alpha=True)
    img.pixels.foreach_set(rgba.ravel())
    path = str(tmp_path / "alpha.png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.ops.s2h.add_reference(filepath=path, view='FRONT', width=80.0)
    ref = bpy.context.active_object
    for source in ('ALPHA', 'LIGHT'):
        select([ref], ref)
        assert bpy.ops.s2h.trace_reference(source=source, mode='FILLED', extrude=False) == {'FINISHED'}
        prof = bpy.context.active_object
        assert prof.s2h_role == 'PROFILE' and len(prof.data.vertices) == 4


def test_finish_variants_and_triangulated_final(scene):
    body = make_box("Body", (20, 20, 20))
    select([body], body)
    assert bpy.ops.s2h.finish(bevel=False, weighted_normal=True) == {'FINISHED'}
    assert [m.type for m in body.modifiers] == ['NODES', 'WEIGHTED_NORMAL']
    assert bpy.ops.s2h.mirror(axis_x=False, axis_z=True, center='OBJECT') == {'FINISHED'}
    assert body.modifiers[0].mirror_object is None
    assert bpy.ops.s2h.mirror(axis_x=False) == {'CANCELLED'}
    select([body], body)
    assert bpy.ops.s2h.make_final(triangulate=True) == {'FINISHED'}
    final = bpy.context.active_object
    assert all(len(p.vertices) == 3 for p in final.data.polygons)
