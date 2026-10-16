"""CPU Blender renderer with articulated humans and cached static poses."""
import bpy
import json
import math
import os
import sys
from pathlib import Path
from mathutils import Vector

cfg = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text())
out = Path(cfg['output'])
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 8
scene.cycles.use_denoising = False
scene.cycles.adaptive_threshold = .15
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.render.resolution_x = 360
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.fps = 12
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.58,.72,.86,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .7


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    return mat


skin = material('warm skin', (.64,.38,.24))
skin2 = material('light skin', (.84,.60,.43))
hair = material('hair', (.045,.024,.015))
blue = material('jacket', (.06,.23,.40))
green = material('coat', (.24,.40,.25))
pants = material('trousers', (.045,.065,.09))
white = material('eyes', (.9,.9,.86))
black = material('pupils', (.015,.018,.02))
wood = material('wood', (.35,.18,.08))


def ball(name, pos, scale, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    if parent:
        obj.parent = parent
    return obj


def cube(name, pos, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new('soft edges', 'BEVEL')
    bevel.width = .05
    bevel.segments = 2
    return obj


def joint(name, pos, parent):
    obj = bpy.data.objects.new(name, None)
    scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = pos
    return obj


def person(name, x, coat, skinmat):
    root = joint(name, (x,0,0), None)
    ball('torso', (0,0,1.25), (.235,.14,.35), coat, root)
    ball('hips', (0,0,.93), (.19,.115,.12), pants, root)
    ball('neck', (0,0,1.63), (.065,.065,.12), skinmat, root)
    ball('face', (0,-.005,1.83), (.14,.13,.20), skinmat, root)
    ball('hair', (0,.018,1.96), (.148,.137,.10), hair, root)
    ball('nose', (0,-.13,1.83), (.026,.032,.045), skinmat, root)
    ball('mouth', (0,-.124,1.765), (.03,.007,.005), hair, root)
    for side in [-1,1]:
        ball('ear', (side*.143,0,1.84), (.023,.033,.055), skinmat, root)
        ball('eye', (side*.054,-.125,1.89), (.023,.012,.012), white, root)
        ball('pupil', (side*.054,-.136,1.89), (.009,.006,.009), black, root)
        ball('brow', (side*.053,-.12,1.924), (.028,.009,.008), hair, root)
    for z in [1.1,1.23,1.36]:
        ball('buttons', (0,-.137,z), (.012,.01,.012), pants, root)
    legs, arms = [], []
    for side in [-1,1]:
        leg = joint('hip joint', (side*.13,0,.94), root)
        ball('trouser leg', (0,0,-.43), (.083,.095,.44), pants, leg)
        ball('shoe', (0,-.075,-.86), (.10,.16,.08), black, leg)
        legs.append(leg)
        arm = joint('shoulder joint', (side*.27,0,1.48), root)
        ball('sleeve', (side*.015,0,-.24), (.075,.085,.27), coat, arm)
        ball('hand', (side*.02,-.015,-.54), (.055,.048,.088), skinmat, arm)
        arms.append(arm)
    return root, legs, arms


a, legs, arms = person('Alex', -1.8, blue, skin)
b, legs2, arms2 = person('Sam', 1.05, green, skin2)
cube('park path', (0,0,-.1), (200,200,.2), material('stone', (.61,.59,.53)))
cube('grass', (0,3,-.08), (25,4,.15), material('grass', (.24,.34,.18)))
for x in [-3,3]:
    cube('trunk', (x,2,1.1), (.22,.22,2.2), wood)
    ball('canopy', (x,2,2.8), (.85,.8,1.1), green)
cube('bench seat', (1.4,1,.55), (1.7,.55,.13), wood)
cube('bench back', (1.4,1.25,.93), (1.7,.12,.65), wood)
for x in [.8,2]:
    cube('bench leg', (x,1,.25), (.1,.4,.5), pants)
parcel = cube('parcel', (.2,-.4,.18), (.34,.3,.32), material('parcel', (.76,.48,.17)))
parcel.hide_render = cfg['story'] == 'reunion'
n = cfg['duration'] * 12
scene.frame_end = n
for frame in range(1,n+1):
    t = (frame-1)/(n-1)
    ax = -1.8 + min(t/.38,1)*1.4
    if t > .8:
        ax = -.4+(t-.8)*4
    a.location.x = ax
    a.keyframe_insert('location', frame=frame)
    b.location.x = 1.05 if t < .8 else 1.05+(t-.8)*3
    b.keyframe_insert('location', frame=frame)
    walking = t < .38 or t > .8
    for i, leg in enumerate(legs):
        leg.rotation_euler.x = math.sin(t*math.pi*24+i*math.pi)*.23 if walking else 0
        leg.keyframe_insert('rotation_euler', frame=frame)
    for i, arm in enumerate(arms):
        arm.rotation_euler.x = math.sin(t*math.pi*24+i*math.pi)*.2 if walking else (-1.0 if .4<t<.65 else 0)
        arm.keyframe_insert('rotation_euler', frame=frame)
    for arm in arms2:
        arm.rotation_euler.x = -.8 if .65<t<.8 else 0
        arm.keyframe_insert('rotation_euler', frame=frame)
    parcel.location = (b.location.x,-.3,1.1) if t>.65 else ((ax+.25,-.3,1.1) if t>.45 else (.2,-.4,.18))
    parcel.keyframe_insert('location', frame=frame)
for obj in [a,b,parcel,*legs,*arms,*arms2]:
    for curve in obj.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
bpy.ops.object.light_add(type='AREA', location=(-3,-4,7))
bpy.context.object.data.energy = 900
bpy.context.object.data.size = 5
bpy.ops.object.camera_add(location=(3.2,-7,3.0))
camera = bpy.context.object
camera.rotation_euler = (Vector((0,0,1.15))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.lens = 48
scene.camera = camera
scene.render.image_settings.file_format = 'PNG'
if cfg['preview']:
    scene.frame_set(int(n*.57))
    scene.render.filepath = str(out/'preview.png')
    bpy.ops.render.render(write_still=True)
else:
    cache = {}
    for frame in range(1,n+1):
        scene.frame_set(frame)
        signature = tuple(round(v,5) for obj in [a,b,parcel,*legs,*arms,*arms2] for row in obj.matrix_world for v in row)
        target = out/f'frame_{frame:04d}.png'
        if signature in cache:
            os.link(cache[signature], target)
        else:
            scene.render.filepath = str(target)
            bpy.ops.render.render(write_still=True)
            cache[signature] = target
