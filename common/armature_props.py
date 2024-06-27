import bpy
from bpy.types import Armature, Bone, Action
from typing import List, Set


class AnmArmature:
	armature: Armature

	def __init__(self, arm_obj):
		self.armature = arm_obj
	
	@property
	def name(self) -> str:
		if ' [C]' in self.armature.name:
			return self.armature.name.removesuffix(' [C]')
		else:
			return self.armature.name

	@property
	def chunk_path(self) -> str:
		return self.armature.xfbin_clump_data.path
	
	@property
	def action(self) -> Action:
		return self.armature.animation_data.action
	
	@property
	def bones(self) -> List[str]:
		bones = self.armature.data.bones

		return [bone.name for bone in bones  if not 'lod' in bone.name]
	
	@property
	def anm_bones(self) -> List[Bone]:
		"""
		Return the bones displayed in the Action channels. 
		"""
		action = self.armature.animation_data.action
		anm_bones = list()

		for curve in action.fcurves:
			data_path = curve.data_path.rpartition('.')[0]
			if (data_path is not ""):
				bone = self.armature.path_resolve(data_path)
				anm_bones.append(bone)

		return list(dict.fromkeys(anm_bones)) # Get unique keys and return as list

	@property
	def materials(self) -> List[str]:
		material_list = list()
		for obj in bpy.data.objects:
			for model in self.armature.xfbin_clump_data.models:
				if bpy.data.objects[model.name]:
					for children in bpy.data.objects[model.name].children:
						for material in children.material_slots:
							if bpy.data.materials[material.name] not in material_list:
								material_list.append(bpy.data.materials[material.name])

		return sorted([mat.name for mat in material_list if not 'lod' in mat.name])
		
	@property
	def models(self) -> List[str]:
		models = self.armature.xfbin_clump_data.models
		
		return [model.name for model in models if not 'lod' in model.name]
	
	
	@property
	def model_indices(self) -> List[int]:
		return [self.models.index(chunk) for chunk in self.models]