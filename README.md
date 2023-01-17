# Ys VIII IT3 mesh export and import
A script to get the mesh data out of IT3 files, hopefully someday will add a way to get mesh data back into the IT3 file.  The output is in .fmt/.vb/.ib files that are compatible with DarkStarSword Blender import plugin for 3DMigoto, and metadata is in JSON format.

## Credits:
99.9% of my understanding of the IT3 format comes from the reverse engineering work of TwnKey (github.com/TwnKey), and specifically TwnKey's model dumper (https://github.com/TwnKey.com/YsVIII_model_dump/).

None of this would be possible without the work of DarkStarSword and his amazing 3DMigoto-Blender plugin, of course.

I am very thankful for TwnKey, uyjulian, DarkStarSword, and the Kiseki modding discord for their brilliant work and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
3. The output can be imported into Blender using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py
4. ys8_it3_export_meshes.py is dependent on lib_fmtibvb.py, which must be in the same folder.  

## Usage:
### ys8_it3_export_meshes.py
Double click the python script and it will search the current folder for all .it3 files and export the meshes into a folder with the same name as the it3 file.  Additionally, it will output a very incomplete JSON file with metadata, which I am using to understand this format further (there is no practical use just yet).

**Command line arguments:**
`ys8_it3_export_meshes.py [-h] [-o] it3_filename`

`-h, --help`
Shows help message.

`-o, --overwrite`
Overwrite existing files without prompting.