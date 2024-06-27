# cc2_anm_export_blender
Animation exporter for CyberConnect2 games (Ultimate Ninja Storm / All Star Battle series).

# 9.7.1 Patch note
### Changes
- Added feature to animate meshes through "Render" button.
> Code for meshes was rewritten.
- Added feature to animate "Alpha", "BlendRate" and "Glare" values.
> You will need to create "Value" nodes (they dont need to be connected with anything) and change their name (not label) to Alpha/BlendRate/Glare to make it work.
- Updated optimize code for animations.
> Now it works with baked animations which had few animated keyframes.
- Changed bone parenting feature.
> To attach bone to another bone (from different armatures), you will need to use "Copy Transforms" modifier instead of "Child Of".

### Fixes
- Fixed issue when models had inverted scales in exported animations if they had inverted scales in bone coordinate values.
> This will help you to deal with situations when model start to look "cursed" if you export animation, it will solve inverted foot bones and etc.
- Fixed issue when scales weren't 1:1 on export.
> To make it work properly, you will need to change "Mapping"'s node type from "Texture" to "Point".

# How to use
## How to export animation.
1. For using that script, you will need to load .xfbin file with CLUMP using Blender XFBIN Addon.
2. Once you loaded clumps in blender, make "Actions" for them (get them somewhere or make them manually from scratch). 
3. When all clumps which you want to export will get actions, open "Scripting" tab and open "exporter.py" script.
4. Select all clumps (armatures) with actions and run that script. 
> [!WARNING]
> Make sure you baked actions before running script!!!

For animation name was used action name of first clump from list of selected clumps.

## How to make copy of clump w/o making new clump in files.
For this feature you will need to make copy of clumps in blender and rename them like that

![image](https://github.com/TheLeonX/cc2_anm_export_blender/assets/92672927/5f2935c4-b1d0-4390-80ad-292c7e080c69)

- Copy clump and add at the end of name "_extra_clump". You can use numbers for it.
- Rename bones using Hydra tools. For example, if it was "1sik00t0", rename it to "1sik05t0".
> That's required for clump referencing.

You can use any amount of clones in animation as soon as they have different bones in armature and "_extra_clump" in name.

# Credits
- [Dei](https://github.com/maxcabd)
- [TheLeonX](https://www.youtube.com/channel/UC5ZOU3R2eWCSGGiAw9pCU6A)
- SutandoTsukai
