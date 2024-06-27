import bpy
from bpy.types import Armature
from mathutils import Matrix, Vector

def get_edit_matrix(armature: bpy.types.Armature, bone_name: str) -> Matrix:
    """
    Get the edit / rest bone matrix.
    """
    if armature is not None:
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')

    bone = armature.data.edit_bones[bone_name]
    arm_mat = dict()

    if armature is not None:
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')

        for arm_bone in armature.data.edit_bones:
            arm_mat[arm_bone.name] = Matrix(arm_bone.get('matrix'))

    mat_parent = arm_mat.get(bone.parent.name, Matrix.Identity(4)) if bone.parent else Matrix.Identity(4)
    mat = arm_mat.get(bone.name, Matrix.Identity(4))
    mat = (mat_parent.inverted() @ mat)

    return mat


def get_current_matrix_loc(armature: Armature, frames: list) -> list:
	adjust_list = list()
	if armature is not None:
		bpy.context.view_layer.objects.active = armature
	for frame in frames:
		bpy.context.scene.frame_set(frame)
		adjust_list.append(armature.matrix_world.to_translation().copy())
	return adjust_list


def get_current_matrix_rot(armature: Armature, frames: list):
	adjust_list = list()
	if armature is not None:
		bpy.context.view_layer.objects.active = armature
	for frame in frames:
		bpy.context.scene.frame_set(frame)
		adjust_list.append(armature.matrix_world.to_quaternion().copy())
	return adjust_list