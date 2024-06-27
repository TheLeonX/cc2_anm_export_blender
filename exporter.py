import os
import sys
import bpy
import json
from time import time
from typing import List, Dict
from bpy.types import Armature, Bone
from mathutils import Quaternion, Euler, Vector

directory, filename = os.path.split(os.path.abspath(bpy.context.space_data.text.filepath))
sys.path.append(directory)

from br.br_anm import *
from br.br_camera import Camera
from br.br_lightdirc import LightDirc
from br.br_lightpoint import LightPoint
from br.br_ambient import Ambient
from common.bone_props import *
from common.armature_props import *
from common.coordinate_converter import *
from common.helpers import *
from common.light_props import *
from common.camera_props import *



is_looped = False # Set to True if your animation should be looped
export_materials = False # Set to True if you want to export material animations
do_optimize = True # Set to False if you don't want to optimize the animation data

anm_chunk_path = "" # Path of anm chunk file


def camera_exists() -> bool:
	""" Return True if Camera exists AND has animation data, and False otherwise."""
	cam = bpy.context.scene.camera

	if cam and cam.animation_data: 
		return True
	else: 
		return False

def light_exists() -> bool:
	"""Returns True if a lightDirc or lightPoint object exists, and False otherwise."""
	lights = get_lights()

	for light in lights:
		if light['type'] == "SUN" or light['type'] == "POINT" or light['type'] == "AREA":
			return True
	return False

def get_anm_armatures() -> List[Armature]:
	"""
	Return list of armatures that contain animation data.
	"""
	anm_armatures: List[Armature] = list()

	for obj in bpy.context.selected_objects:
		if obj.type == "ARMATURE":
			armature_obj = bpy.data.objects[obj.name]

			if armature_obj.animation_data:
				anm_armatures.append(armature_obj)

	return anm_armatures

# Animated armature objects which are special objects with .anm properties
animated_armatures = list(map(lambda x: AnmArmature(x), get_anm_armatures()))


def make_mapping_reference(types=False) -> List[str]:
	"""
	Create ExtraMapping Reference list of clump, coord, material, model names for all animated armatures.
	"""
	extra_mapping_reference: List[str] = list()
	extra_mapping_reference_types: List[str] = list()
	
	if types:
		for armature_obj in animated_armatures:
			bones = list(map(lambda x: x + 'nuccChunkCoord', armature_obj.bones))
			materials = list(map(lambda x: x + 'nuccChunkMaterial', armature_obj.materials))
			models = list(map(lambda x: x + 'nuccChunkModel', armature_obj.models))

			 # Check if models is empty, if so use armature_obj.bones[0] instead
			if not armature_obj.models:
				extra_mapping_reference_types.extend([armature_obj.bones[0] + 'nuccChunkClump', *bones, *materials])
			else:
				extra_mapping_reference_types.extend([armature_obj.models[0] + 'nuccChunkClump', *bones, *materials, *models])
		
		return extra_mapping_reference_types
		
	else:
		for armature_obj in animated_armatures:
			if not armature_obj.models:
				extra_mapping_reference.extend([armature_obj.bones[0], *armature_obj.bones, *armature_obj.materials])
			else:
				extra_mapping_reference.extend([armature_obj.models[0], *armature_obj.bones, *armature_obj.materials])
		return extra_mapping_reference
		

# Create ExtraMapping Reference list of clump, coord, material, model names for all animated armatures. 
extra_mapping_reference: List[str] = make_mapping_reference()
extra_mapping_reference_types: List[str] = make_mapping_reference(types=True) # With types


def make_clump(armature: AnmArmature, clump_index: int) -> Clump:
	"""
	Create clump struct based on armatures index and bone / model indices.
	"""

	# Get bone material indices from extra mapping reference
	bone_material_indices: List[int]
	model_indices: List[int]

	bones = list(map(lambda x: x + 'nuccChunkCoord', armature.bones))
	materials = list(map(lambda x: x + 'nuccChunkMaterial', armature.materials))
	
	bone_material_map = [*bones, *materials]

	models = list()
	for model in armature.models:
		#if not bpy.data.objects[model].hide_render:
		models.append(model)

	model_map = list(map(lambda x: x + 'nuccChunkModel', models))

	bone_material_indices = [extra_mapping_reference_types.index(bone_material) for bone_material in bone_material_map]
	model_indices = [extra_mapping_reference_types.index(model) for model in model_map]

	clump = Clump(
				clump_index, 
				len(bone_material_indices), 
				len(model_indices), 
				bone_material_indices, 
				model_indices)

	return clump


def make_clumps() -> List[Clump]:
	"""
	Create multiple clump structs based on the animated armatures present.
	"""
	clumps: List[Clump] = list()

	for armature_obj in animated_armatures:
		# Create clump struct and add to list
		if not len(armature_obj.models):
			clump_index = extra_mapping_reference_types.index(armature_obj.bones[0] + 'nuccChunkClump')
		else:
			clump_index = extra_mapping_reference_types.index(armature_obj.models[0] + 'nuccChunkClump')
		clump = make_clump(armature_obj, clump_index)
		clumps.append(clump)
	return clumps


def make_coord_parent() -> CoordParent:
	"""
	Create coord parent structs for all animated armatures.
	"""
	anm_coords: List[AnmCoord] = list()
	obj_arm_name_list = list()
	obj_arm_list = get_anm_armatures()
	for arm in obj_arm_list:
		obj_arm_name_list.append(arm.name)
	for index, armature_obj in enumerate(animated_armatures):
		children: List[Bone] = [bone for bone in armature_obj.armature.data.bones if bone.parent] # List of child bones

		for bone in children:
			parent = AnmCoord(index, armature_obj.bones.index(bone.parent.name))
			child = AnmCoord(index, armature_obj.bones.index(bone.name))
			anm_coords.extend([parent, child])
		all_bones: List[Bone] = armature_obj.armature.data.bones

		for bone in all_bones:
			if ("Copy Transforms" in obj_arm_list[index].pose.bones[bone.name].constraints):
				parent_clump_index = obj_arm_name_list.index(obj_arm_list[index].pose.bones[bone.name].constraints["Copy Transforms"].target.name)

				parent = AnmCoord(parent_clump_index,animated_armatures[parent_clump_index].bones.index(obj_arm_list[index].pose.bones[bone.name].constraints["Copy Transforms"].subtarget))
				child = AnmCoord(index, armature_obj.bones.index(bone.name))
				anm_coords.extend([parent, child])

	return CoordParent(anm_coords)


def add_curve(curve_format: AnmCurveFormat, curve_index: int, curve_size: int, frame_count: int, values: List, curve_headers: List[CurveHeader], curves: List[Curve]):
	"""
	Add curve to curve_headers and curves list.
	"""
	curve = Curve(curve_format, values)
	curves.append(curve)
	curve_header = CurveHeader(curve_index, curve_format.value, frame_count, curve_size)
	curve_headers.append(curve_header)

def make_entry_light(light_index: int) -> Entry:
	"""
	Make .anm Entry struct for lightPoint and LightDirc object.. 
	"""
	curve_headers: List[CurveHeader] = list()
	curves: List[Curve] = list()

	light = get_lights()[light_index]

	light_type = light['type']
	light_color_values = light['color']
	light_strength_values = light['strength']
	light_pos_values = light['matrix_world']
	light_rot_values = light['matrix_world_rotation']
	

	if (light_type == "POINT"):
		light_radius_1_values = light['size']
		light_radius_2_values = light['size_2']

		# Combine the color, strength, and rotation values into one list so we can use an index to create the curves
		light_values = {
			'color': light_color_values,
			'strength': light_strength_values,
			'position': light_pos_values,
			'radius_1': light_radius_1_values,
			'radius_2': light_radius_2_values
		}



		# Create curves for each value
		for index, (key, values) in enumerate(light_values.items()):
			if key == 'color':
				converted_values = [[value * 255 for value in sublist] for sublist in light_values[key]]
				chained_values = chain_list(converted_values)
				frame_count = len(converted_values)

				if len(converted_values) % 4 != 0:
					# Pad the list with the last value so the length is a multiple of 4
					chained_values += converted_values[-1] * (4 - len(converted_values) % 4)
					frame_count = len(converted_values) + (4 - len(converted_values) % 4)
				add_curve(AnmCurveFormat.BYTE3, index, 24, frame_count, chained_values, curve_headers, curves)
			
			if key == 'strength':
				converted_values = convert_light_values('light_strength', light_values[key])
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 4, len(converted_values), converted_values, curve_headers, curves)
			
			if key == 'position':
				keyframe_vec3 = dict()
				converted_values = convert_light_values('light_pos', light_pos_values)

				if len(light_pos_values) > 1:
					for frame, value in enumerate(converted_values):
						keyframe_vec3[frame * 100] = value

					keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key

					frame_count = len(light_pos_values) + 1
					add_curve(AnmCurveFormat.INT1_FLOAT3, index, 24, frame_count, keyframe_vec3, curve_headers, curves)
			
			if key == 'radius_1':
				converted_values = convert_light_values('light_radius', light_radius_1_values)
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)

			if key == 'radius_2':
				converted_values = convert_light_values('light_radius', light_radius_2_values)
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)

		# Create the entry
		clump_index = -1
		coord_index = light_index
		entry_format = EntryFormat.LIGHTPOINT # LightPoint
		curve_count = len(curve_headers)

		entry = Entry(clump_index, coord_index, entry_format, curve_count, curve_headers, curves)

		
	if (light_type == "SUN"):
		# Combine the color, strength, and rotation values into one list so we can use an index to create the curves
		light_values = {
			'color': light_color_values,
			'strength': light_strength_values,
			'rotation': light_rot_values
		}

		# Create the curves
		for index, (key, values) in enumerate(light_values.items()):
			if key == 'color':
				converted_values = [[value * 255 for value in sublist] for sublist in light_values[key]]
				chained_values = chain_list(converted_values)
				frame_count = len(converted_values)

				if len(converted_values) % 4 != 0:
					# Pad the list with the last value so the length is a multiple of 4
					chained_values += converted_values[-1] * (4 - len(converted_values) % 4)
					frame_count = len(converted_values) + (4 - len(converted_values) % 4)
				add_curve(AnmCurveFormat.BYTE3, index, 24, frame_count, chained_values, curve_headers, curves)

			if key == 'strength':
				converted_values = convert_light_values('light_strength', light_values[key])
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)
			
			if key == 'rotation':
				if len(light_values[key]) < 2:
					converted_values = convert_light_values('light_rot_euler', light_values[key])
					frame_count = len(converted_values)
					add_curve(AnmCurveFormat.FLOAT3ALT, index, 24, frame_count, converted_values, curve_headers, curves)
				else:
					converted_values = convert_light_values('light_rot', light_values[key])
					frame_count = len(converted_values)
					add_curve(AnmCurveFormat.SHORT4, index, 24, frame_count, converted_values, curve_headers, curves)

		# Create the entry
		clump_index = -1
		coord_index = light_index
		entry_format = EntryFormat.LIGHTDIRECTION
		curve_count = len(curve_headers)

		entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	if (light_type == "AREA"):
		# Combine the color, strength, and rotation values into one list so we can use an index to create the curves
		light_values = {
			'color': light_color_values,
			'strength': light_strength_values
		}

		# Create the curves
		for index, (key, values) in enumerate(light_values.items()):
			if key == 'color':
				converted_values = [[value * 255 for value in sublist] for sublist in light_values[key]]
				chained_values = chain_list(converted_values)
				frame_count = len(converted_values)

				if len(converted_values) % 4 != 0:
					# Pad the list with the last value so the length is a multiple of 4
					chained_values += converted_values[-1] * (4 - len(converted_values) % 4)
					frame_count = len(converted_values) + (4 - len(converted_values) % 4)
				add_curve(AnmCurveFormat.BYTE3, index, 24, frame_count, chained_values, curve_headers, curves)

			if key == 'strength':
				converted_values = convert_light_values('light_strength', light_values[key])
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)

		# Create the entry
		clump_index = -1
		coord_index = light_index
		entry_format = EntryFormat.AMBIENT
		curve_count = len(curve_headers)

		entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	return entry


def make_entry_camera() -> Entry:
	"""
	Make .anm Entry struct for camera object. An entry is equivalent to an Action Group in Blender. 
	"""
	curve_headers: List[CurveHeader] = list()
	curves: List[Curve] = list()

	camera = get_camera()

	camera_FOV = camera['FOV']
	camera_pos_values = camera['matrix_world']
	camera_rot_values = camera['matrix_world_rotation']
	
	# Combine the color, strength, and rotation values into one list so we can use an index to create the curves
	camera_values = {
		'position': camera_pos_values,
		'rotation': camera_rot_values,
		'FOV': camera_FOV
	}


	# Create curves for each value
	for index, (key, values) in enumerate(camera_values.items()):
		
		
		if key == 'position':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_pos', camera_values[key])

			if len(camera_pos_values) > 1:
				for frame, value in enumerate(converted_values):
					keyframe_vec3[frame * 100] = value

				keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key

				frame_count = len(camera_pos_values) + 1
				add_curve(AnmCurveFormat.INT1_FLOAT3, index, 24, frame_count, keyframe_vec3, curve_headers, curves)
		
		if key == 'rotation':
			if len(camera_values[key]) < 2:
				converted_values = convert_camera_values('camera_rot_euler', camera_values[key])
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT3ALT, index, 24, frame_count, converted_values, curve_headers, curves)
			else:
				converted_values = convert_camera_values('camera_rot', camera_values[key])
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.SHORT4, index, 24, frame_count, converted_values, curve_headers, curves)

		if key == 'FOV':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', camera_values[key])

			if len(camera_pos_values) > 1:
				for frame, value in enumerate(converted_values):
					keyframe_vec3[frame * 100] = value

				keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key

				frame_count = len(camera_FOV) + 1
				add_curve(AnmCurveFormat.INT1_FLOAT1, index, 24, frame_count, keyframe_vec3, curve_headers, curves)

	# Create the entry
	clump_index = -1
	coord_index = 0
	entry_format = EntryFormat.CAMERA # Camera
	curve_count = len(curve_headers)

	entry = Entry(clump_index, coord_index, entry_format, curve_count, curve_headers, curves)

	return entry

def get_bone_action_frames(action_name: str, bone_name: str, channel_id: int):
    fcurves = bpy.data.actions[action_name].groups.get(bone_name)
    keyframes = list()
    
    
    for keyframe in fcurves.channels[channel_id].keyframe_points:
        keyframes.append(int(keyframe.co[0]))
    return keyframes

def delete_bone_frame_for_optimize(action_name: str, bone_name: str):
	fcurves = bpy.data.actions[action_name].groups.get(bone_name).channels
	keyframes = list()
	count = len(fcurves[0].keyframe_points)
    
	if (count > 2):
		i = 1
		while (i < count-1):
			location_1 = Vector((fcurves[0].keyframe_points[i-1].co[1],
			fcurves[1].keyframe_points[i].co[1],
			fcurves[2].keyframe_points[i].co[1]))
			rotation_1 = Quaternion((fcurves[3].keyframe_points[i-1].co[1],
			fcurves[4].keyframe_points[i].co[1],
			fcurves[5].keyframe_points[i].co[1],
			fcurves[6].keyframe_points[i].co[1]))
			
			location_2 = Vector((fcurves[0].keyframe_points[i].co[1],
			fcurves[1].keyframe_points[i].co[1],
			fcurves[2].keyframe_points[i].co[1]))
			rotation_2 = Quaternion((fcurves[3].keyframe_points[i].co[1],
			fcurves[4].keyframe_points[i].co[1],
			fcurves[5].keyframe_points[i].co[1],
			fcurves[6].keyframe_points[i].co[1]))

			location_3 = Vector((fcurves[0].keyframe_points[i+1].co[1],
			fcurves[1].keyframe_points[i].co[1],
			fcurves[2].keyframe_points[i].co[1]))
			rotation_3 = Quaternion((fcurves[3].keyframe_points[i+1].co[1],
			fcurves[4].keyframe_points[i].co[1],
			fcurves[5].keyframe_points[i].co[1],
			fcurves[6].keyframe_points[i].co[1]))
			
			if (location_1 == location_2 == location_3) and (rotation_1 == rotation_2 == rotation_3):
				keyframes.append(int(fcurves[0].keyframe_points[i].co[0]))

			i = i + 1

	return keyframes

def make_entry_bone(armature_obj: Armature, bone_name: str, clump_index: int, clump: Clump, parent_exist: bool = True) -> Entry:
	"""
	Make .anm Entry struct. An entry is equivalent to an Action Group in Blender. 
	"""
	action = armature_obj.animation_data.action
	curve_headers: List[CurveHeader] = list()
	curves: List[Curve] = list()

	# Make animated armature object and clump
	bone_material_indices: List[int] = clump.bone_material_indices

	mat = get_edit_matrix(armature_obj, bone_name)
	loc, rot, sca = mat.decompose()
	group = action.groups.get(bone_name)
	fcurves = group.channels
	
	data_paths = dict()
	
	channel_count = len(fcurves)
	loc_channel_values = list()
	rot_channel_values = list()
	scale_channel_values = list()

	loc_updated_frames = get_bone_action_frames(action.name,bone_name,0)
	rot_updated_frames = get_bone_action_frames(action.name,bone_name,3)
	scale_updated_frames = get_bone_action_frames(action.name,bone_name,7)

	
	optimize_frames = list()
	if (do_optimize):
		optimize_frames = delete_bone_frame_for_optimize(action.name, bone_name)

    #location
	for i in range(channel_count):
		path = fcurves[i].data_path.rpartition('.')[2]
		keyframes = [int(k) for k in range(len(fcurves[i].keyframe_points))]
		data_paths[path] = len(keyframes) # Add keyframe count

		loc_channel_values.append(list(map(lambda key: fcurves[i].evaluate(key), loc_updated_frames)))

	#rotation
	for i in range(channel_count):
		path = fcurves[i].data_path.rpartition('.')[2]
		keyframes = [int(k) for k in range(len(fcurves[i].keyframe_points))]
		data_paths[path] = len(keyframes) # Add keyframe count

		rot_channel_values.append(list(map(lambda key: fcurves[i].evaluate(key), rot_updated_frames)))
	#scale
	for i in range(channel_count):
		path = fcurves[i].data_path.rpartition('.')[2]
		keyframes = [int(k) for k in range(len(fcurves[i].keyframe_points))]
		data_paths[path] = len(keyframes) # Add keyframe count
		scale_channel_values.append(list(map(lambda key: fcurves[i].evaluate(key), scale_updated_frames)))

	scale_adjust = 0
	for data_path, keyframe_count in data_paths.items():
		if data_path == 'location':
			keyframe_vec3 = dict()
			if (parent_exist):
				values = list(
					map(lambda x, y, z,: Vector((x, y, z)), 
					loc_channel_values[0], 
					loc_channel_values[1], 
					loc_channel_values[2]))
				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)
			else:
				adjust_loc_values = get_current_matrix_loc(armature_obj,loc_updated_frames)
				values = list(
					map(lambda x, y, z, adjust: Vector((x+adjust[0], y+adjust[1], z+adjust[2])), 
					loc_channel_values[0], 
					loc_channel_values[1], 
					loc_channel_values[2], adjust_loc_values))
				converted_values = convert_to_anm_values("location_camera", values, loc, rot, sca)
			
			for frame, value in enumerate(converted_values):
					if loc_updated_frames[frame] not in optimize_frames:
						keyframe_vec3[loc_updated_frames[frame] * 100] = value
			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT3, list(data_paths).index(data_path), 12, keyframe_count + 1-len(optimize_frames), keyframe_vec3, curve_headers, curves)
		if data_path == 'rotation_euler' or data_path == 'rotation_quaternion':
			keyframe_vec3 = dict()
			if (parent_exist):
				if (data_path == 'rotation_euler'):
					scale_adjust = 1
					values = list(map(lambda x, y, z: Euler(Vector((x, y, z))).to_quaternion(), rot_channel_values[3], rot_channel_values[4], rot_channel_values[5]))
				elif (data_path == 'rotation_quaternion'):
					values = list(map(lambda w, x, y, z: Quaternion((w, x, y, z)), rot_channel_values[3], rot_channel_values[4], rot_channel_values[5], rot_channel_values[6])) 
				converted_values = convert_to_anm_values('rotation_quaternion_keyframe', values, loc, rot, sca)
			else:
				adjust_rot_values = get_current_matrix_rot(armature_obj,rot_updated_frames)
				if (data_path == 'rotation_euler'):
					scale_adjust = 1
					values = list(map(lambda x, y, z, adjust: adjust @ Euler(Vector((x, y, z))).to_quaternion(), rot_channel_values[3], rot_channel_values[4], rot_channel_values[5], adjust_rot_values))
				elif (data_path == 'rotation_quaternion'):
					values = list(map(lambda w, x, y, z, adjust: adjust @ Quaternion((w, x, y, z)), rot_channel_values[3], rot_channel_values[4], rot_channel_values[5], rot_channel_values[6], adjust_rot_values)) 
				converted_values = convert_camera_values('camera_rot', values)
			
			for frame, value in enumerate(converted_values):
					if rot_updated_frames[frame] not in optimize_frames:
						keyframe_vec3[rot_updated_frames[frame] * 100] = value
			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT4, list(data_paths).index(data_path), 12, keyframe_count + 1-len(optimize_frames), keyframe_vec3, curve_headers, curves)

		if data_path == 'scale':
			keyframe_vec3 = dict()
			values = list(
					map(lambda x, y, z: Vector((x, y, z)), 
					scale_channel_values[7-scale_adjust], 
					scale_channel_values[8-scale_adjust], 
					scale_channel_values[9-scale_adjust]))
			converted_values = convert_to_anm_values('scale_keyframe', values, loc, rot, sca)
			for frame, value in enumerate(converted_values):
					if scale_updated_frames[frame] not in optimize_frames:
						keyframe_vec3[scale_updated_frames[frame] * 100] = value
			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT3, list(data_paths).index(data_path), 12, keyframe_count + 1-len(optimize_frames), keyframe_vec3, curve_headers, curves)
	
	# Add toggled visibility curve
	if parent_exist:
		'''add_curve(AnmCurveFormat.FLOAT1, 3, 12, 1, [1], curve_headers, curves)'''
		keyframe_vec3 = dict()
		values = list()
		values = get_toggle_values_bone(bone_name)
		for frame, value in enumerate(values):
				keyframe_vec3[frame * 100] = value
		keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
		add_curve(AnmCurveFormat.INT1_FLOAT1, 3, 12, len(keyframe_vec3), keyframe_vec3, curve_headers, curves)

	else:
		'''add_curve(AnmCurveFormat.SHORT1, 3, len(values) * 2, len(values), values, curve_headers, curves)'''
		keyframe_vec3 = dict()
		values = list()
		values = get_toggle_values(armature_obj.name)
		for frame, value in enumerate(values):
				keyframe_vec3[frame * 100] = value
		keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
		add_curve(AnmCurveFormat.INT1_FLOAT1, 3, 12, len(keyframe_vec3), keyframe_vec3, curve_headers, curves)


	coord_index = bone_material_indices.index(extra_mapping_reference_types.index(group.name + 'nuccChunkCoord'))
	entry_format = EntryFormat.BONE
	curve_count = len(curve_headers)

	entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	return entry

def get_toggle_values(armature_name: str) -> list():
	values = list()
	for frame in range(bpy.context.scene.frame_end):
		bpy.context.scene.frame_set(frame)
		if bpy.data.objects[armature_name].hide_render:
			values.append(0)
		else:
			values.append(1)
	values.append(values[-1])
	return values

def get_toggle_values_bone(bone_name: str) -> list():
	values = list()
	for obj in bpy.context.scene.objects:
		if obj.xfbin_nud_data.mesh_bone == bone_name:
			for frame in range(bpy.context.scene.frame_end):
				bpy.context.scene.frame_set(frame)
				if obj.hide_render:
					values.append(0)
				else:
					values.append(1)
			values.append(values[-1])
			return values
	values.append(1)
	return values

@dataclass
class MaterialEntry:
	loc_x_1uv: float = 0
	loc_y_1uv: float = 0
	scale_x_1uv: float = 1
	scale_y_1uv: float = 1
	loc_x_2uv: float = 0
	loc_y_2uv: float = 0
	scale_x_2uv: float = 1
	scale_y_2uv: float = 1
	blend_v: float = 0
	glare_v: float = 0.12
	alpha_v: float = 205


def get_material_values(material_name: str) -> list():
	values = list()
	for frame in range(bpy.context.scene.frame_end):
		bpy.context.scene.frame_set(frame)
		frame = MaterialEntry()
		if "Mapping" in bpy.data.materials[material_name].node_tree.nodes:
			frame.loc_x_1uv = bpy.data.materials[material_name].node_tree.nodes["Mapping"].inputs[1].default_value[0]
			frame.loc_y_1uv = bpy.data.materials[material_name].node_tree.nodes["Mapping"].inputs[1].default_value[1]
			frame.scale_x_1uv = bpy.data.materials[material_name].node_tree.nodes["Mapping"].inputs[3].default_value[0]
			frame.scale_y_1uv = bpy.data.materials[material_name].node_tree.nodes["Mapping"].inputs[3].default_value[1]
		elif "UV_0_Mapping" in bpy.data.materials[material_name].node_tree.nodes:
			frame.loc_x_1uv = bpy.data.materials[material_name].node_tree.nodes["UV_0_Mapping"].inputs[1].default_value[0]
			frame.loc_y_1uv = bpy.data.materials[material_name].node_tree.nodes["UV_0_Mapping"].inputs[1].default_value[1]
			frame.scale_x_1uv = bpy.data.materials[material_name].node_tree.nodes["UV_0_Mapping"].inputs[3].default_value[0]
			frame.scale_y_1uv = bpy.data.materials[material_name].node_tree.nodes["UV_0_Mapping"].inputs[3].default_value[1]
		if "UV_1_Mapping" in bpy.data.materials[material_name].node_tree.nodes:
			frame.loc_x_2uv = bpy.data.materials[material_name].node_tree.nodes["UV_1_Mapping"].inputs[1].default_value[0]
			frame.loc_y_2uv = bpy.data.materials[material_name].node_tree.nodes["UV_1_Mapping"].inputs[1].default_value[1]
			frame.scale_x_2uv = bpy.data.materials[material_name].node_tree.nodes["UV_1_Mapping"].inputs[3].default_value[0]
			frame.scale_y_2uv = bpy.data.materials[material_name].node_tree.nodes["UV_1_Mapping"].inputs[3].default_value[1]
		if "UV_0_Mapping" and "UV_1_Mapping" and "BlendRate"  in bpy.data.materials[material_name].node_tree.nodes:
			frame.blend_v = bpy.data.materials[material_name].node_tree.nodes["BlendRate"].outputs[0].default_value
		if "Glare"  in bpy.data.materials[material_name].node_tree.nodes:
			frame.glare_v = bpy.data.materials[material_name].node_tree.nodes["Glare"].outputs[0].default_value
		if "Alpha"  in bpy.data.materials[material_name].node_tree.nodes:
			frame.alpha_v = bpy.data.materials[material_name].node_tree.nodes["Alpha"].outputs[0].default_value
		values.append(frame)
	
	return values

def make_entry_material(material_name: str, clump_index: int, clump: Clump) -> Entry:
	"""
	Make .anm Entry struct for material. An entry is equivalent to an Action Group in Blender. 
	"""
	curve_headers: List[CurveHeader] = list()
	curves: List[Curve] = list()

	bone_material_indices: List[int] = clump.bone_material_indices


	values = get_material_values(material_name)


	loc_values_x_1UV = list()
	loc_values_y_1UV = list()
	scale_values_x_1UV = list()
	scale_values_y_1UV = list()
	loc_values_x_2UV = list()
	loc_values_y_2UV = list()
	scale_values_x_2UV = list()
	scale_values_y_2UV = list()
	blend_value = list()
	glare_value = list()
	alpha_value = list()

	for frame in values:
		loc_values_x_1UV.append(frame.loc_x_1uv)
		loc_values_y_1UV.append((-1*frame.scale_y_1uv)+1-frame.loc_y_1uv)
		scale_values_x_1UV.append(frame.scale_x_1uv)
		scale_values_y_1UV.append(frame.scale_y_1uv)
		loc_values_x_2UV.append(frame.loc_x_2uv)
		loc_values_y_2UV.append((-1*frame.scale_y_2uv)+1-frame.loc_y_2uv)
		scale_values_x_2UV.append(frame.scale_x_2uv)
		scale_values_y_2UV.append(frame.scale_y_2uv)
		blend_value.append(frame.blend_v)
		glare_value.append(frame.glare_v)
		alpha_value.append(frame.alpha_v)
	
	material_values = {
		'location_X_1UV': loc_values_x_1UV,
		'location_Y_1UV': loc_values_y_1UV,
		'scale_X_1UV': scale_values_x_1UV,
		'scale_Y_1UV': scale_values_y_1UV,
		'location_X_2UV': loc_values_x_2UV,
		'location_Y_2UV': loc_values_y_2UV,
		'scale_X_2UV': scale_values_x_2UV,
		'scale_Y_2UV': scale_values_y_2UV,
		'blend': blend_value,
		'glare': glare_value,
		'alpha': alpha_value
	}


	# Create curves for each value
	for index, (key, values) in enumerate(material_values.items()):
		
		
		if key == 'location_X_1UV': 
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 0, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #X location 1UV
		
		if key == 'location_Y_1UV':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 1, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #Y location 1UV
		
		if key == 'location_X_2UV': 
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 2, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #X location 2UV
		
		if key == 'location_Y_2UV':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 3, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #Y location 2UV
		
		if key == 'scale_X_1UV':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 8, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #X scale 1UV
		
		if key == 'scale_Y_1UV':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 9, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #Y scale 1UV
		if key == 'scale_X_2UV':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 10, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #X scale 2UV
		
		if key == 'scale_Y_2UV':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 11, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #Y scale 2UV
		
		if key == 'blend':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 12, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #blend value
		
		if key == 'glare':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 15, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #glare value
		
		if key == 'alpha':
			keyframe_vec3 = dict()
			converted_values = convert_camera_values('camera_FOV', material_values[key])
			for frame, value in enumerate(converted_values):
				keyframe_vec3[frame * 100] = value

			keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
			add_curve(AnmCurveFormat.INT1_FLOAT1, 16, 24, len(keyframe_vec3), keyframe_vec3, curve_headers, curves) #alpha value

	add_curve(AnmCurveFormat.FLOAT1, 4, 12, 1, [0], curve_headers, curves) #celshade param setting !NEVER DELETE THAT!

	
	'''
	add_curve(AnmCurveFormat.FLOAT1, 5, 12, 1, [0], curve_headers, curves)
	add_curve(AnmCurveFormat.FLOAT1, 6, 12, 1, [0], curve_headers, curves)
	add_curve(AnmCurveFormat.FLOAT1, 7, 12, 1, [0], curve_headers, curves)
	'''
	'''
	add_curve(AnmCurveFormat.FLOAT1, 13, 12, 1, [0], curve_headers, curves)
	add_curve(AnmCurveFormat.FLOAT1, 14, 12, 1, [0], curve_headers, curves)'''
	'''add_curve(AnmCurveFormat.FLOAT1, 15, 12, 1, [0.13], curve_headers, curves)''' #Glare
	'''add_curve(AnmCurveFormat.FLOAT1, 16, 12, 1, [205], curve_headers, curves)''' #Field02
	'''add_curve(AnmCurveFormat.FLOAT1, 17, 12, 1, [1], curve_headers, curves)'''

	# Create the entry
	coord_index = bone_material_indices.index(extra_mapping_reference_types.index(material_name + 'nuccChunkMaterial'))
	entry_format = EntryFormat.MATERIAL
	curve_count = len(curve_headers)

	entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	return entry


def make_entries() -> list[Entry]:
	"""
	Make entries for all bones and armatures.
	"""
	entries: List[Entry] = list()

	for armature_obj in animated_armatures:
		anm_bones: List[Bone] = armature_obj.anm_bones
		anm_materials: list() = armature_obj.materials

		clump: Clump = make_clump(AnmArmature(armature_obj.armature), animated_armatures.index(armature_obj))

		for bone in anm_bones:
			parent_exist = False

			if bone.parent:
				parent_exist = True

			e: Entry = make_entry_bone(armature_obj.armature, bone.name, animated_armatures.index(armature_obj), clump, parent_exist)

			if do_optimize:
				clean_entry(e) # Remove duplicate keyframes from entry
		
			entries.append(e)
			
		if export_materials:
			for material in anm_materials:
				if "UV_1_Location" or "UV_2_Location" or "UV_1_Scale" or "UV_2_Scale" in bpy.data.materials[material].node_tree.nodes:

					e: Entry = make_entry_material(material, animated_armatures.index(armature_obj), clump)
					entries.append(e)

	# If there is a camera in the scene, create an entry for it
	if camera_exists():
		entries.append(make_entry_camera())

	# If there are light objects in the scene, create entries for each of them
	if light_exists():
		lights = get_lights()

		for light in lights:
			if light['type'] in ["SUN", "POINT", "AREA"]:
				entries.append(make_entry_light(lights.index(light)))
	
	return entries

def clean_entry(entry: Entry) -> None:
	"""
	Remove duplicate keyframes from entry.
	"""
	header: CurveHeader
	curve: Curve

	for (header, curve) in zip(entry.curve_headers, entry.curves):
		if curve.curve_format == AnmCurveFormat.INT1_FLOAT3:
			values = curve.keyframes.values()
			unique_values = list(set(values))

			if len(unique_values) == 1:
				first_value = list(curve.keyframes.values())[0]

	
				curve.keyframes.clear()
				curve.keyframes: Tuple[float] = first_value # Convert to tuple
				curve.curve_format = AnmCurveFormat.FLOAT3

				header.frame_count = 1
				header.curve_format = AnmCurveFormat.FLOAT3
		
		if curve.curve_format == AnmCurveFormat.INT1_FLOAT4:
			values = curve.keyframes.values()
			unique_values = list(set(values))

			if len(unique_values) == 1:
				first_value = {list(curve.keyframes.items())[0][0]: list(curve.keyframes.items())[0][1]}

				curve.keyframes.clear()

				curve.keyframes = first_value
				curve.keyframes.update({-1: [*curve.keyframes.values()][-1]}) # Add null key

				header.frame_count = len(curve.keyframes)


		if curve.curve_format == AnmCurveFormat.INT1_FLOAT1:
			values = curve.keyframes.values()
			unique_values = list(set(values))

			if len(unique_values) == 1:
				first_value = list(curve.keyframes.values())[0]

	
				curve.keyframes.clear()

				# TODO: Toggled curves are a list of a tuple, we don't need it to be a list, fix it in the future
				curve.keyframes: List[Tuple[float]] = [first_value] # Convert to tuple
				curve.curve_format = AnmCurveFormat.FLOAT1

				header.frame_count = 1
				header.curve_format = AnmCurveFormat.FLOAT1

# For debug purposes
def timed(func):
	def inner(*args, **kwargs):
		t0 = time()

		result = func(*args, **kwargs)
		elapsed = time() - t0
		print(f'Animation exported in {elapsed} seconds')

		return result

	return inner


@timed
def make_anm() -> bytearray:
	"""
	Make anm buffer and return it.
	"""
	clumps = make_clumps()
	entries = make_entries()
	coord_parent = make_coord_parent()
	
	entry_count = len(entries)
	clump_count = len(clumps)
	coord_count = len(coord_parent.anm_coords) // 2

	other_entry_count = 0

	if camera_exists():
		other_entry_count += 1

	if light_exists():
		lights = get_lights()

		for light in lights:
			if light['type'] == "SUN":
				other_entry_count += 1
			if light['type'] == "POINT":
				other_entry_count += 1
			if light['type'] == "AREA":
				other_entry_count += 1
	
	# TODO: Get the frame length from the Action itself
	# action = obj.animation_data.action
	# start_frame, end_frame = action.frame_range
	# frame_length = end_frame - start_frame + 1

	frame_length = bpy.context.scene.frame_end


	anm = Anm(frame_length, 1, entry_count, is_looped, 
					clump_count, other_entry_count, coord_count,
					clumps, coord_parent, entries)

	with BinaryReader(endianness=Endian.BIG) as anm_writer:
		anm_writer.write_struct(anm)

		return anm_writer.buffer()


def make_camera() -> bytearray:
	"""
	Make camera buffer and return it.
	"""
	unk1 = 0
	fov = 45.0

	cam = Camera(unk1, fov)

	with BinaryReader(endianness=Endian.BIG) as cam_writer:
		cam_writer.write_struct(cam)

		return cam_writer.buffer()

def make_lightdirc() -> bytearray:
	"""
	Make lightDirc buffer and return it.
	"""
	unk1 = 0
	unk2 = 0
	unk3 = 0
	unk4 = 0
	unk5 = 0.521569
	unk6 = 0.827451
	unk7 = 1
	unk8 = 1
	unk9 = 0
	unk10 = 0
	unk11 = 0
	unk12 = 0
	unk13 = -0.185349
	unk14 = 0.438735
	unk15 = -0.181711
	unk16 = 0.860313

	lightdirc = LightDirc(unk1,unk2,unk3,unk4,unk5,unk6,unk7,unk8,unk9,unk10,unk11,unk12,unk13,unk14,unk15,unk16)

	with BinaryReader(endianness=Endian.BIG) as lightdirc_writer:
		lightdirc_writer.write_struct(lightdirc)

		return lightdirc_writer.buffer()

def make_lightpoint() -> bytearray:
	"""
	Make lightPoint buffer and return it.
	"""
	unk1 = 0
	unk2 = 0
	unk3 = 0
	unk4 = 0
	unk5 = 0.0392157
	unk6 = 0.117647
	unk7 = 1
	unk8 = 0
	unk9 = 0
	unk10 = -23.2275
	unk11 = -183.9
	unk12 = 111.04
	unk13 = 100
	unk14 = 400
	unk15 = 0
	unk16 = 0

	lightpoint = LightPoint(unk1,unk2,unk3,unk4,unk5,unk6,unk7,unk8,unk9,unk10,unk11,unk12,unk13,unk14,unk15,unk16)

	with BinaryReader(endianness=Endian.BIG) as lightpoint_writer:
		lightpoint_writer.write_struct(lightpoint)

		return lightpoint_writer.buffer()

def make_ambient() -> bytearray:
	"""
	Make Ambient buffer and return it.
	"""
	unk1 = 0.290196
	unk2 = 0.494118
	unk3 = 0.611765
	unk4 = 1


	ambient = Ambient(unk1,unk2,unk3,unk4)

	with BinaryReader(endianness=Endian.BIG) as ambient_writer:
		ambient_writer.write_struct(ambient)

		return ambient_writer.buffer()

def write_buffers():
	""" Write buffers to file. """
	export_path = f'{directory}\\Exported Animations'

	action_name = animated_armatures[0].action.name
	
	anm_path = f'{export_path}\\[000] {action_name} (nuccChunkAnm)'
	anm_filename = f'{action_name}.anm'

	if not os.path.exists(anm_path):
		os.makedirs(anm_path)
	
	# Write the ANM file
	with open(f'{anm_path}\\{anm_filename}', 'wb+') as anm:
		anm.write(make_anm())
	
	# Write the CAM file, if a camera exists
	if camera_exists():
		cam_filename = 'camera01.camera'
		with open(f'{anm_path}\\{cam_filename}', 'wb+') as cam:
			cam.write(make_camera())

	# Write the LIGHT files
	if light_exists():
		light_types = {
			"SUN": (".lightdirc", make_lightdirc),
			"POINT": (".lightpoint", make_lightpoint),
			"AREA": (".ambient", make_ambient),
		}

		for i, light in enumerate(get_lights()):
			name = light['name'] + str(i + 1).zfill(2)
			light_type = light['type']
			light_filename = name + light_types[light_type][0]

			with open(f'{anm_path}\\{light_filename}', 'wb+') as light:
				light.write(light_types[light_type][1]())
		

def write_json():
	""" Write page json to file. """
	chunk_maps: List[Dict] = [{"Name": "", "Type": "nuccChunkNull", "Path": ""}]
	chunk_references: List[Dict] = list()
	chunks: List[Dict] = list()

	# Create camera chunks
	if camera_exists():
		cam_path = animated_armatures[0].chunk_path
		cam_name = 'camera01'

		cam_chunk: Dict = make_chunk_dict(cam_path, cam_name, "nuccChunkCamera", reference=False, file=False)
		chunk_maps.append(cam_chunk)

		cam_file_chunk: Dict = make_chunk_dict(cam_path, cam_name, "nuccChunkCamera", reference=False, file=True)
		chunks.append(cam_file_chunk)

	# Create light chunks
	if light_exists():
		for i, light in enumerate(get_lights()):
			if light['type'] == "POINT":
				lightpoint_path = animated_armatures[0].chunk_path
				lightpoint_name = light['name'] + str(i + 1).zfill(2)

				lightpoint_chunk: Dict = make_chunk_dict(lightpoint_path, lightpoint_name, "nuccChunkLightPoint", reference=False, file=False)
				chunk_maps.append(lightpoint_chunk)

				lightpoint_file_chunk: Dict = make_chunk_dict(lightpoint_path, lightpoint_name, "nuccChunkLightPoint", reference=False, file=True)
				chunks.append(lightpoint_file_chunk)
			
			if light['type'] == "SUN":
				lightdirc_path = animated_armatures[0].chunk_path
				lightdirc_name = light['name'] + str(i + 1).zfill(2)

				lightdirc_chunk: Dict = make_chunk_dict(lightdirc_path, lightdirc_name, "nuccChunkLightDirc", reference=False, file=False)
				chunk_maps.append(lightdirc_chunk)

				lightdirc_file_chunk: Dict = make_chunk_dict(lightdirc_path, lightdirc_name, "nuccChunkLightDirc", reference=False, file=True)
				chunks.append(lightdirc_file_chunk)
			if light['type'] == "AREA":
				ambient_path = animated_armatures[0].chunk_path
				ambient_name = light['name'] + str(i + 1).zfill(2)

				ambient_chunk: Dict = make_chunk_dict(ambient_path, ambient_name, "nuccChunkAmbient", reference=False, file=False)
				chunk_maps.append(ambient_chunk)

				ambient_file_chunk: Dict = make_chunk_dict(ambient_path, ambient_name, "nuccChunkAmbient", reference=False, file=True)
				chunks.append(ambient_file_chunk)

	# Create ANM chunk
	if animated_armatures:
		if anm_chunk_path == "":
			anm_path = animated_armatures[0].chunk_path
		else:
			anm_path = anm_chunk_path

		anm_name = animated_armatures[0].action.name

		anm_chunk: Dict = make_chunk_dict(anm_path, anm_name, "nuccChunkAnm", reference=False, file=False)
		chunk_maps.append(anm_chunk)

		anm_file_chunk: Dict = make_chunk_dict(anm_path, anm_name, "nuccChunkAnm", reference=False, file=True)
		chunks.append(anm_file_chunk)
	
	for armature_obj in animated_armatures:
		path = armature_obj.chunk_path

		if ("extra_clump" not in armature_obj.name):
			# Add clump chunk and reference dictionary
			clump_chunk, clump_ref = make_chunk_dict(path, armature_obj.name, "nuccChunkClump", clump=armature_obj)
			chunk_maps.append(clump_chunk)
			chunk_references.append(clump_ref)
			
			# Add coord, material, model chunks and references dictionaries
			for bone_name in armature_obj.bones:
				coord_chunk, coord_ref = make_chunk_dict(path, bone_name, "nuccChunkCoord")
				chunk_maps.append(coord_chunk)
				chunk_references.append(coord_ref)

			for mat_name in armature_obj.materials:
				mat_chunk, mat_ref = make_chunk_dict(path, mat_name, "nuccChunkMaterial")
				chunk_maps.append(mat_chunk)
				chunk_references.append(mat_ref)
			
			for model_name in armature_obj.models:
				model_chunk, model_ref = make_chunk_dict(path, model_name, "nuccChunkModel")
				chunk_maps.append(model_chunk)
				chunk_references.append(model_ref)
		else:
			ref_armature_index = -1
			ref_armature_name = ""
			for ex_armature in animated_armatures:
				if (armature_obj.name in ex_armature.name):
					ref_armature_name = ex_armature.name[:ex_armature.name.find(" [C]_extra_clump")]
			for idx,ex_armature in enumerate(animated_armatures):
				if (ref_armature_name == ex_armature.name):
					ref_armature_index = idx

			# Add clump chunk and reference dictionary
			clump_ref = make_chunk_dict_ref(path, bpy.data.objects[armature_obj.name].data.name, ref_armature_name, "nuccChunkClump")
			chunk_references.append(clump_ref)
			
			# Add coord, material, model chunks and references dictionaries
			for idx, bone_name in enumerate(armature_obj.bones):
				coord_ref = make_chunk_dict_ref(path, bone_name, animated_armatures[ref_armature_index].bones[idx], "nuccChunkCoord")
				chunk_references.append(coord_ref)

			for idx, mat_name in enumerate(armature_obj.materials):
				mat_ref = make_chunk_dict_ref(path, mat_name,animated_armatures[ref_armature_index].materials[idx], "nuccChunkMaterial")
				chunk_references.append(mat_ref)
			
			for idx, model_name in enumerate(armature_obj.models):
				model_ref = make_chunk_dict_ref(path, model_name,animated_armatures[ref_armature_index].models[idx], "nuccChunkModel")
				chunk_references.append(model_ref)
		
	page_chunk = make_chunk_dict("", "Page0", "nuccChunkPage", reference=False, file=False)
	chunk_maps.append(page_chunk)

	index_chunk = make_chunk_dict("", "index", "nuccChunkIndex", reference=False, file=False)
	chunk_maps.append(index_chunk)


	page_json = dict()
	page_json['Chunk Maps'] = list(map(lambda x: x, chunk_maps))
	page_json['Chunk References'] = list(map(lambda x: x, chunk_references))
	page_json['Chunks'] = list(map(lambda x: x, chunks))

	export_path = f'{directory}\\Exported Animations'
	page_path = export_path + '\\[000] ' + animated_armatures[0].action.name +' (nuccChunkAnm)'

	if not os.path.exists(page_path):
		os.makedirs(page_path)

	with open(os.path.join(page_path, '_page.json'), 'w', encoding='cp932') as file:
		json.dump(page_json, file, ensure_ascii=False, indent=4)


write_buffers()
write_json()