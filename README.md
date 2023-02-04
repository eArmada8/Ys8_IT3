# Ys VIII IT3 mesh and texture export
A script to get the mesh data and textures out of IT3 files, hopefully someday I will find a way to get both back into the IT3 file.  The mesh output is in .fmt/.vb/.ib files that are compatible with DarkStarSword Blender import plugin for 3DMigoto, textures are in DDS format, and metadata is in JSON format.

## Credits:
99.9% of my understanding of the IT3 format comes from the reverse engineering work of TwnKey (github.com/TwnKey), and specifically TwnKey's model dumper (https://github.com/TwnKey.com/YsVIII_model_dump/).

None of this would be possible without the work of DarkStarSword and his amazing 3DMigoto-Blender plugin, of course.

I am very thankful for TwnKey, uyjulian, DarkStarSword, and the Kiseki modding discord for their brilliant work and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
3. The output can be imported into Blender using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py  ("4D" position and normal data import must be enabled.)
4. ys8_it3_export_meshes.py is dependent on lib_fmtibvb.py, which must be in the same folder.  

## Usage:
### ys8_it3_export_meshes.py
Double click the python script and it will search the current folder for all .it3 files and export the meshes and textures into a folder with the same name as the it3 file.  Additionally, it will output a very incomplete JSON file with metadata, which I am using to understand this format further (there is no practical use just yet).

**Command line arguments:**
`ys8_it3_export_meshes.py [-h] [-c] [-t] [-o] it3_filename`

`-h, --help`
Shows help message.

`-c, --completemaps`
.vgmap files will have the entire skeleton, with every bone available to the mesh, included with each mesh.  This will result in many empty vertex groups upon import into Blender.  The default behavior is to only include vertex groups that contain at least one vertex.  Complete maps are primarily useful when merging one mesh into another.

`-t, --trim_for_gpu`
Trim vertex buffer for GPU injection (3DMigoto).  Meshes in the IT3 file have 18 vertex buffer semantics.  Only 12 of these are actually loaded into GPU memory.  This option produces smaller .vb files (with matching .fmt files) with the extraneous buffers discarded, so that the buffers can be used for injection with 3DMigoto.

`-o, --overwrite`
Overwrite existing files without prompting.

### ys8_it3_to_basic_gltf.py
Double click the python script to run and it will attempt to convert the IT3 model into a basic glTF model, with skeleton.  This tool as written is for obtaining the skeleton for rigging the .fmt/.ib/.vb/.vgmap meshes from the export tool.  *The meshes included in the model are not particularly useful as they cannot be exported back to IT3,* just delete them and import the exported meshes (.fmt/.ib/.vb./vgmap) instead - the tool only includes meshes because Blender refuses to open a glTF file without meshes.  After importing the meshes, Ctrl-click on the armature and parent (Object -> Parent -> Armature Deform {without the extra options}).

It will search the current folder for it3 files and convert them all, unless you use command line options.

**Command line arguments:**
`ys8_it3_to_basic_gltf.py [-h] [-n] [-r] [-o] it3_filename`

`-h, --help`
Shows help message.

`-n, --no_axis_flip`
Ys VIII models has a Y up / -X forward orientation, the default behavior of the glTF conversion is to rotate the models to Z up / Y forward orientation by rotating the base node 90 degrees and transforming the position and normal data.  (The exporter does not do this, the user is expected to select Z up / Y forward on import in Blender so that exports can be used properly in game.  glTF import does not allow axis selection though, so this transform is needed.)  Use this option to override the default behavior and skip the transform.

`-r, --render_no_skel`
As the Ys VIII models have world objects / bounding boxes etc that have no skeleton, the script by default skips including these since they are not useful in the glTF for weight painting etc.  If this option is invoked, the meshes without skeleton (weight groups) will be included in the glTF.

`-o, --overwrite`
Overwrite existing files without prompting.
