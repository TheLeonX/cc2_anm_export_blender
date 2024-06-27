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

# Credits
- [Dei](https://github.com/maxcabd)
- [TheLeonX](https://www.youtube.com/channel/UC5ZOU3R2eWCSGGiAw9pCU6A)
- SutandoTsukai
