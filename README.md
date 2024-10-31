# Ys VIII / IX IT3 mesh and texture export
A script to get the mesh data and textures into and out of IT3 files.  IT3 rebuilding is highly experimental at this time.  The mesh output is in .fmt/.vb/.ib files that are compatible with DarkStarSword Blender import plugin for 3DMigoto, textures are in DDS format, and metadata is in JSON format.  Model extraction is successfully tested with Ys VIII / IX models so far, with limited support for Ys VII and Ys Memories of Celceta as well.  (It is conceivable that some other games using VPA8 or newer, such as Legend of Nayuta, may be supported, but these games are untested.)  Import supports only Ys VIII / Ys IX models at this time.

## Tutorials:

Please see the [wiki](https://github.com/eArmada8/Ys8_IT3/wiki), and the detailed documentation below.

## Credits:
99.9% of my understanding of the IT3 format comes from the reverse engineering work of [TwnKey](https://github.com/TwnKey), and specifically [TwnKey's model dumper](https://github.com/TwnKey/IT3Dumper), for which I am eternally grateful.  Also a huge thank you [uyjulian](https://github.com/uyjulian), for generously giving me the Falcom bz decompression algorithm from his [IT3 parser](https://gist.github.com/uyjulian/a6ba33dc29858327ffa0db57f447abe5).  Thank you to [Kyuuhachi](https://github.com/Kyuuhachi) for sharing his extensive findings on the structure of ITP and VPA8 as well, and his patient explanations of literally everything.

None of this would be possible without the work of DarkStarSword and his amazing 3DMigoto-Blender plugin, of course.

I am very thankful for TwnKey, uyjulian, Kyuuhachi, lm, DarkStarSword, and the Kiseki modding discord for their brilliant work and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
3. The output can be imported into Blender using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py (tested on commit [5fd206c](https://raw.githubusercontent.com/DarkStarSword/3d-fixes/5fd206c52fb8c510727d1d3e4caeb95dac807fb2/blender_3dmigoto.py))  ("4D" position and normal data import must be enabled.)
4. ys8_it3_export_assets.py is dependent on lib_fmtibvb.py, which must be in the same folder.  

## Usage:

### ys8_it3_export_assets.py
Double click the python script and it will search the current folder for all .it3 files and export the meshes and textures into a folder with the same name as the it3 file.  Additionally, it will output a JSON file with all the material metadata, which is used at the time of repacking the it3 to rebuild the material data (RTY2 and MAT6 blocks).

In regards to textures, for Ys 8 and 9 models (modern TEXI/TEX2 blocks) the script will output DDS files.  Older games, the script will output raw ITP files (Falcom format).  Please use [Cradle](https://github.com/Aureole-Suite/Cradle/releases/) by Kyuuhachi to convert the ITP files into useable PNG files.

**Command line arguments:**
`ys8_it3_export_assets.py [-h] [-c] [-t] [-o] it3_filename`

`-h, --help`
Shows help message.

`-p, --partialmaps`
.vgmap files will have the entire skeleton, with every bone available to the mesh, included with each mesh.  This will result in many empty vertex groups upon import into Blender.  This option will cause the script to only include vertex groups that contain at least one vertex.

`-g, --preserve_gl_order`
By default, the script will change the order of the triangles from OpenGL format to Direct3D format (from counter-clockwise to clockwise) for better compatibility with Blender and glTF.  This switch preserves the original index buffer order.  (Note that for import, the order will be converted back, so do not use this option for modding the game.)

`-t, --trim_for_gpu`
Trim vertex buffer for GPU injection (3DMigoto).  Meshes in the IT3 file have 18 vertex buffer semantics.  Only 12 of these are actually loaded into GPU memory.  This option produces smaller .vb files (with matching .fmt files) with the extraneous buffers discarded, so that the buffers can be used for injection with 3DMigoto.

`-i, --always_write_itp`
The default behavior of the script is to output ITP files only if they cannot be converted into DDS textures.  This option will direct the script to output both DDS and ITP files (particularly useful if the DDS files are incorrect / broken).

`-o, --overwrite`
Overwrite existing files without prompting.

### ys8_it3_import_assets.py
Double click the python script and it will search the current folder for all .it3 files with exported folders, and import the meshes and textures in the folder back into the it3 file.  This script requires a working it3 file already be present as it does not reconstruct the entire file; only the known relevant sections.  The remaining parts of the file (the skeleton and any animation data, etc) are copied unaltered from the intact it3 file.  By default, it will apply c77 compression to the relevant blocks (or bz mode 2 if VPA9 blocks are detected).

Meshes are attached to existing VPA9/VPAX/VP11 blocks, and are found using the name of the block followed by an underscore (which matches the output from ys8_it3_export_assets.py).  For example, if the import script finds a VPAX block in the `c005_ps4_main2`, it will search for meshes with the following names: `meshes/c005_ps4_main2_*.vb`.  It will replace *all* the meshes associated with that node within the .it3 with *all* the meshes that it finds.  Therefore, if the .it3 has `c005_ps4_main2_00` through `c005_ps4_main2_02` for example, deleting `c005_ps4_main2_01.vb` will remove it from the VPAX, and a new mesh `c005_ps4_main2_03.vb` if found, will be added to the block.  A new BBOX and MAT6 (bounding box and material section, respectively) will replace the old block.

If all the submeshes of a mesh node are deleted, then the script will insert a blank invisible mesh in its place so that the node remains intact.  This is required to prevent crashes, and also allow for mesh importation in the future (if the VPAX block is removed, the script will not know to look for meshes in the future under that node).

*Every submesh* must have its own .material file with a valid material to be included into MAT6; submeshes without .material files will be ignored by the import script.  These files contain a *pointer* to material_metadata.json.  The actual materials (with shader parameters, textures, etc) are all in material_metadata.json.  Every .material file (and thus every submesh) *must* point to a valid entry inside material_metadata.json.  We do not know the values for most of the materials; however, the UV wrapping variables have been identified and are the 3rd and 4th texture flags (each texture has 4 flags underneath the texture name).  The values are 0: REPEAT, 1: CLAMP_TO_EDGE, 2: MIRRORED_REPEAT.

If there is a .bonemap file (same format as .vgmap, should be the name of the node - so `c005_ps4_main2.bonemap`, not `c005_ps4_main2_00.bonemap`), then a new BON3 section will be written to change the bone palette of the *entire mesh node*.  (For example, if a new submesh `c005_ps4_main2_03` is added and requires a new bone map, then `c005_ps4_main2_00` and every other submesh *must* also use that new bone map).

It will make a backup of the original, then overwrite the original.  It will not overwrite backups; for example if "model.it3.bak" already exists, then it will write the backup to "model.it3.bak1", then to "model.it3.bak2", and so on.

**Command line arguments:**
`ys8_it3_import_assets.py [-h] it3_filename`

`-n, --import_noskel`
The default behavior of the script is to skip over non-rendered meshes such as hitboxes and copy those directly from the IT3.  This command will instruct the script to treat those meshes as it would rendered meshes, and import them from .fmt/.ib/.vb (or delete them if the meshes are absent).  If using ys8_it3_to_basic_gltf.py and ys8_gltf_to_meshes.py, be warned that the default behavior of ys8_it3_to_basic_gltf.py is to omit these meshes, so using this option will result in loss of the non-rendered meshes unless you also use the `--render_no_skel` option in ys8_it3_to_basic_gltf.py.

`-h, --help`
Shows help message.

### ys8_it3_to_basic_gltf.py
Double click the python script to run and it will attempt to convert the IT3 model into a basic glTF model, with skeleton.  This tool as written is for obtaining the skeleton for rigging the .fmt/.ib/.vb/.vgmap meshes from the export tool.  *The meshes included in the model are not particularly useful as they cannot be exported back to IT3,* just delete them and import the exported meshes (.fmt/.ib/.vb./vgmap) instead - the tool only includes meshes because Blender refuses to open a glTF file without meshes.  After importing the meshes, Ctrl-click on the armature and parent (Object -> Parent -> Armature Deform {without the extra options}).

The script has *very* basic texture support for IT3 files with MAT4/MAT6 blocks.  Place all the textures required in a 'textures' folder in the same folder as the .gltf file, in .png format.

It will search the current folder for it3 files and convert them all, unless you use command line options.

**Command line arguments:**
`ys8_it3_to_basic_gltf.py [-h] [-n] [-r] [-o] it3_filename`

`-h, --help`
Shows help message.

`-n, --no_axis_flip`
Ys models has a Y up / -X forward orientation, the default behavior of the glTF conversion is to rotate the models to Z up / Y forward orientation by rotating the base node 90 degrees and transforming the position, normal and tangent data.  (The exporter does not do this, the user is expected to select Z up / Y forward on import in Blender so that exports can be used properly in game.  glTF import does not allow axis selection though, so this transform is needed.)  Use this option to override the default behavior and skip the transform.

`-r, --render_no_skel`
As the Ys models have world objects / bounding boxes etc that have no skeleton, the script by default skips including these since they are not useful in the glTF for weight painting etc.  If this option is invoked, the meshes without skeleton (weight groups) will be included in the glTF.  (This filters by RTY2 material variant, removing objects with a value of 8.  Thus non-skeletal objects meant to be rendered, such as eyes, will still be rendered.)

`-o, --overwrite`
Overwrite existing files without prompting.

### ys8_gltf_to_meshes.py
Double click the python script to run, and it will attempt to pull the meshes and bone palettes out of each glTF file it finds (.glb or .gltf).  It will write to the same folder that ys8_it3_export_assets.py writes to.  It does not output materials, but it will output a material file with the name of the material in the glTF - each of these files *must* be replaced with a real material from the game.  Textures must be provided (in .dds format) as well.  The script will output a bonemap for writing the BON3 section; if you are not changing the bone palette then delete the .bonemap file to use the original BON3 section from the IT3, especially if your meshes are not rendering.

**Command line arguments:**
`ys8_gltf_to_meshes.py [-h] [-c] [-o] mdl_filename`

`-h, --help`
Shows help message.

`-p, --partialmaps`
.vgmap files will have the entire skeleton, with every bone available to the mesh, included with each mesh.  This will result in many empty vertex groups upon import into Blender.  This option changes the script behavior to only include vertex groups that contain at least one vertex.

`-d, --dontrotate`
Ys models has a Y up / -X forward orientation.  Since the default behavior of the glTF conversion is to rotate the models to Z up / Y forward orientation, the default behavior of this script is to reverse that rotation by applying a -90 degree rotation on the X axis.  This option instructs the script to skip that step.

`-o, --overwrite`
Overwrite existing files without prompting.

