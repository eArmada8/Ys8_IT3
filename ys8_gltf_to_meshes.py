# Tool to extract the meshes and bone palette from glTF files.
# Usage:  Run by itself without commandline arguments and it will read every .glb/.gltf file
# and extract the meshes.
#
# For command line options, run:
# /path/to/python3 ys8_gltf_to_skeleton.py --help
#
# Requires pygltflib, which can be installed by:
# /path/to/python3 -m pip install pygltflib
#
# Requires both lib_fmtibvb.py and ys8_it3_export_assets.py, which should be in the same directory.
#
# GitHub eArmada8/Ys8_IT3

try:
    import numpy, math, json, io, struct, re, os, sys, glob
    from pygltflib import GLTF2
    from ys8_it3_export_assets import *
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

# This script outputs complete vgmaps by default, change the following line to False to change
complete_vgmaps_default = True

def accessor_stride(gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    componentSize = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    componentCount = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    return(componentCount[accessor.type] * componentSize[accessor.componentType])

#Does not support sparse
def read_stream (gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    bufferview = gltf.bufferViews[accessor.bufferView]
    buffer = gltf.buffers[bufferview.buffer]
    componentType = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
    componentCount = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    componentFormat = "<{0}{1}".format(componentCount[accessor.type],\
        componentType[accessor.componentType])
    componentStride = accessor_stride(gltf, accessor_num)
    data = []
    with io.BytesIO(gltf.get_data_from_buffer_uri(buffer.uri)) as f:
        f.seek(bufferview.byteOffset + accessor.byteOffset, 0)
        for i in range(accessor.count):
            data.append(list(struct.unpack(componentFormat, f.read(componentStride))))
            if (bufferview.byteStride is not None) and (bufferview.byteStride > componentStride):
                f.seek(bufferview.byteStride - componentStride, 1)
    if accessor.normalized == True:
        for i in range(len(data)):
            if componentType == 'b':
                data[i] = [x / ((2**(8-1))-1) for x in data[i]]
            elif componentType == 'B':
                data[i] = [x / ((2**8)-1) for x in data[i]]
            elif componentType == 'h':
                data[i] = [x / ((2**(16-1))-1) for x in data[i]]
            elif componentType == 'H':
                data[i] = [x / ((2**16)-1) for x in data[i]]
    return(data)

def dxgi_format (gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    RGBAD = ['R','G','B','A','D']
    bytesize = {5120:'8', 5121: '8', 5122: '16', 5123: '16', 5125: '32', 5126: '32'}
    elementtype = {5120: 'SINT', 5121: 'UINT', 5122: 'SINT', 5123: 'UINT', 5125: 'UINT', 5126: 'FLOAT'}
    normelementtype = {5120: 'SNORM', 5121: 'UNORM', 5122: 'SNORM', 5123: 'UNORM'}
    numelements = {'SCALAR':1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
    dxgi_format = "".join([RGBAD[i]+bytesize[accessor.componentType] \
        for i in range(numelements[accessor.type])]) + '_'
    if accessor.normalized == True:
        dxgi_format += normelementtype[accessor.componentType]
    else:
        dxgi_format += elementtype[accessor.componentType]
    return(dxgi_format)

#adapted from concept3d @ stackexchange, thank you!
def calc_tangents (submesh):
    #If IB is flat list, convert to triangles
    if isinstance(submesh['ib'][0], list) is False:
        triangles = [[submesh['ib'][i*3],submesh['ib'][i*3+1], submesh['ib'][i*3+2]] for i in range(len(submesh['ib'])//3)]
    else:
        triangles = list(submesh['ib'])
    posBuffer = [x['Buffer'] for x in submesh['vb'] if x['SemanticName'] == 'POSITION'][0]
    if len(posBuffer[0]) > 3:
        posBuffer = [x[0:3] for x in posBuffer]
    normBuffer = [numpy.array(x['Buffer']) for x in submesh['vb'] if x['SemanticName'] == 'NORMAL'][0]
    if len(normBuffer[0]) > 3:
        normBuffer = [x[0:3] for x in normBuffer]
    texBuffer = [x['Buffer'] for x in submesh['vb'] if x['SemanticName'] == 'TEXCOORD' and x['SemanticIndex'] == '0'][0]
    if len(texBuffer[0]) > 2:
        texBuffer = [x[0:2] for x in texBuffer]
    tanBuffer = []
    binormalBuffer = []
    tan1 = [numpy.array([0.0,0.0,0.0]) for i in range(len(posBuffer))]
    tan2 = [numpy.array([0.0,0.0,0.0]) for i in range(len(posBuffer))]
    for i in range(len(triangles)):
        x1 = posBuffer[triangles[i][1]][0] - posBuffer[triangles[i][0]][0]
        x2 = posBuffer[triangles[i][1]][0] - posBuffer[triangles[i][0]][0]
        y1 = posBuffer[triangles[i][1]][1] - posBuffer[triangles[i][0]][1]
        y2 = posBuffer[triangles[i][2]][1] - posBuffer[triangles[i][0]][1]
        z1 = posBuffer[triangles[i][1]][2] - posBuffer[triangles[i][0]][2]
        z2 = posBuffer[triangles[i][2]][2] - posBuffer[triangles[i][0]][2]
        s1 = texBuffer[triangles[i][1]][0] - texBuffer[triangles[i][0]][0]
        s2 = texBuffer[triangles[i][2]][0] - texBuffer[triangles[i][0]][0]
        t1 = texBuffer[triangles[i][1]][1] - texBuffer[triangles[i][0]][1]
        t2 = texBuffer[triangles[i][2]][1] - texBuffer[triangles[i][0]][1]
        if (s1 * t2 - s2 * t1) == 0:
            r = 1.0 / 0.000001
        else:
            r = 1.0 / (s1 * t2 - s2 * t1)
        sdir = numpy.array([(t2 * x1 - t1 * x2) * r, (t2 * y1 - t1 * y2) * r,\
                    (t2 * z1 - t1 * z2) * r]);
        tdir = numpy.array([(s1 * x2 - s2 * x1) * r, (s1 * y2 - s2 * y1) * r,\
                    (s1 * z2 - s2 * z1) * r]);
        tan1[triangles[i][0]] += sdir
        tan1[triangles[i][1]] += sdir
        tan1[triangles[i][2]] += sdir
        tan2[triangles[i][0]] += tdir
        tan2[triangles[i][1]] += tdir
        tan2[triangles[i][2]] += tdir
    for a in range(len(posBuffer)):
        vector = tan1[a] - normBuffer[a] * numpy.dot(normBuffer[a], tan1[a])
        if not numpy.linalg.norm(vector) == 0.0:
            vector = vector / numpy.linalg.norm(vector)
        if numpy.dot(numpy.cross(normBuffer[a], tan1[a]), tan2[a]) < 0:
            handedness = -1
        else:
            handedness = 1
        tanBuffer.append(vector.tolist())
        binormalBuffer.append((numpy.cross(normBuffer[a], vector) * handedness).tolist())
    return (tanBuffer, binormalBuffer)

def dump_meshes (mesh_node, gltf, rotate_model = True, complete_maps = True):
    basename = mesh_node.name
    mesh = gltf.meshes[mesh_node.mesh]
    if mesh_node.skin is not None:
        skin = gltf.skins[mesh_node.skin]
        vgmap = {gltf.nodes[skin.joints[i]].name:i for i in range(len(skin.joints))}
    submeshes = []
    for i in range(len(mesh.primitives)):
        submesh = {'name': '{0}_{1:02d}'.format(basename, i)}
        print("Reading mesh {0}...".format(submesh['name']))
        tops = {0: 'pointlist', 4: 'trianglelist', 5: 'trianglestrip'}
        submesh['fmt'] = make_fmt(0xFFFF,2)
        submesh['ib'] = [x for y in read_stream(gltf, mesh.primitives[i].indices) for x in y]
        elements = []
        Semantics = ['POSITION', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NORMAL', 'TANGENT', 'COLOR_0', 'COLOR_1',\
            'TEXCOORD_0', 'TEXCOORD_1', 'TEXCOORD_2', 'UNKNOWN', 'WEIGHTS_0', 'UNKNOWN', 'JOINTS_0', 'UNKNOWN']
        SemanticName = ['POSITION', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NORMAL', 'TANGENT', 'COLOR', 'COLOR', 'TEXCOORD',\
            'TEXCOORD', 'TEXCOORD', 'UNKNOWN', 'BLENDWEIGHTS', 'UNKNOWN', 'BLENDINDICES', 'UNKNOWN']
        SemanticIndex = ['0', '0', '1', '2', '0', '0', '0', '1', '0', '1', '2', '3', '0', '4', '0', '5']
        # We will assume that POSITION always exists, hopefully this is not foolish.
        accessor = getattr(mesh.primitives[i].attributes, 'POSITION')
        pos_buffer = read_stream(gltf, accessor)
        num_vertices = len(pos_buffer)
        if len(pos_buffer[0]) == 3:
            pos_buffer = [x+[0.0] for x in pos_buffer]
        submesh['vb'] = [{'SemanticName': SemanticName[0], 'SemanticIndex': SemanticIndex[0], 'Buffer': pos_buffer}]
        for j in range(1,16):
            if j in [1,2,3,11,13,15] or not hasattr(mesh.primitives[i].attributes, Semantics[j]) \
                or getattr(mesh.primitives[i].attributes, Semantics[j]) is None:
                if j == 6: # COLOR_0
                    submesh['vb'].append({'SemanticName': SemanticName[j], 'SemanticIndex': SemanticIndex[j],\
                        'Buffer': [[1,1,1,1] for _ in range(num_vertices)]})
                elif j == 7: # COLOR_1
                    submesh['vb'].append({'SemanticName': SemanticName[j], 'SemanticIndex': SemanticIndex[j],\
                        'Buffer': [[0,0,0,1] for _ in range(num_vertices)]})
                else:
                    #Note if TANGENT is missing, garbage data will be inserted at this step, and replaced once we have TEXCOORD_0
                    submesh['vb'].append({'SemanticName': SemanticName[j], 'SemanticIndex': SemanticIndex[j],\
                        'Buffer': [[0,0,0,0] for _ in range(num_vertices)]})
            else:
                accessor = getattr(mesh.primitives[i].attributes, Semantics[j])
                buffer = read_stream(gltf, accessor)
                while len(buffer[0]) < 4:
                    if j < 6 and len(buffer[0]) == 3:
                        buffer = [x+[1] for x in buffer]
                    else:
                        buffer = [x+[0] for x in buffer]
                submesh['vb'].append({'SemanticName': SemanticName[j], 'SemanticIndex': SemanticIndex[j],\
                    'Buffer': buffer})
        if rotate_model == True:
            for j in [0,4,5]:
                submesh['vb'][j]['Buffer'] = [[x[0],-x[2],x[1],x[3]] for x in submesh['vb'][j]['Buffer']]
        if not hasattr(mesh.primitives[i].attributes, 'TANGENT') or getattr(mesh.primitives[i].attributes, 'TANGENT') is None:
            tangentBuf, binormalBuf = calc_tangents (submesh)
            while len(tangentBuf[0]) < 4:
                tangentBuf = [x+[1.0] for x in tangentBuf]
            submesh['vb'][5]['Buffer'] = tangentBuf
        if mesh_node.skin is not None:
            vgs_i = [i for i in range(len(submesh['vb'])) if submesh['vb'][i]['SemanticName'] == 'BLENDINDICES']
            if complete_maps == False and len(vgs_i) > 0:
                used_vgs = list(set([x for y in submesh['vb'][vgs_i[0]]['Buffer'] for x in y]))
                submesh['vgmap'] = {k:v for (k,v) in vgmap.items() if v in used_vgs }
            else:
                submesh['vgmap'] = dict(vgmap)
        if mesh.primitives[i].material is not None:
            submesh['material'] = gltf.materials[mesh.primitives[i].material].name
        else:
            submesh['material'] = 'None'
        submeshes.append(submesh)
    return(submeshes)

def process_gltf (gltf_filename, rotate_model = True, complete_maps = complete_vgmaps_default, overwrite = False):
    print("Processing {0}...".format(gltf_filename))
    try:
        model_gltf = GLTF2().load(gltf_filename)
    except:
        print("File {} not found, or is invalid, skipping...".format(gltf_filename))
        return False
    model_name = gltf_filename.split('.gl')[0]
    if os.path.exists(model_name) and (os.path.isdir(model_name)) and (overwrite == False):
        if str(input(model_name + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(model_name):
        if not os.path.exists(model_name+'/meshes'):
            os.makedirs(model_name+'/meshes')
        mesh_nodes = [x for x in model_gltf.nodes if x.mesh is not None]
        mesh_metadata = []
        for mesh_node in mesh_nodes:
            submeshes = dump_meshes(mesh_node, model_gltf, rotate_model=rotate_model, complete_maps = complete_maps)
            for i in range(len(submeshes)):
                write_fmt(submeshes[i]['fmt'], '{0}/meshes/{1}.fmt'.format(model_name, submeshes[i]['name']))
                write_ib(submeshes[i]['ib'], '{0}/meshes/{1}.ib'.format(model_name, submeshes[i]['name']), submeshes[i]['fmt'])
                write_vb(submeshes[i]['vb'], '{0}/meshes/{1}.vb'.format(model_name, submeshes[i]['name']), submeshes[i]['fmt'])
                if 'vgmap' in submeshes[i]:
                    with open('{0}/meshes/{1}.vgmap'.format(model_name, submeshes[i]['name']), 'wb') as f:
                        f.write(json.dumps(submeshes[i]['vgmap'], indent=4).encode("utf-8"))
                if 'material' in submeshes[i]:
                    with open('{0}/meshes/{1}.material'.format(model_name, submeshes[i]['name']), 'wb') as f:
                        f.write(json.dumps({'material_name': submeshes[i]['material']}, indent=4).encode("utf-8"))
            if 'vgmap' in submeshes[0]:
                with open('{0}/meshes/{1}.bonemap'.format(model_name, mesh_node.name), 'wb') as f:
                    f.write(json.dumps(submeshes[i]['vgmap'], indent=4).encode("utf-8"))
            
    return True

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        if complete_vgmaps_default == True:
            parser.add_argument('-p', '--partialmaps', help="Provide vgmaps with non-empty groups only", action="store_false")
        else:
            parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire mesh skeleton", action="store_true")
        parser.add_argument('-d', '--dontrotate', help="Do not change Y-up to Z-up (-90 degree rotation on X axis)", action="store_false")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('gltf_filename', help="Name of gltf file to export from (required).")
        args = parser.parse_args()
        if complete_vgmaps_default == True:
            complete_maps = args.partialmaps
        else:
            complete_maps = args.completemaps
        if os.path.exists(args.gltf_filename) and len(args.gltf_filename.lower().split('.gl')) > 1:
            process_gltf(args.gltf_filename, rotate_model = args.dontrotate, complete_maps = complete_maps, overwrite = args.overwrite)
    else:
        gltf_files = glob.glob('*.gl*')
        for i in range(len(gltf_files)):
            process_gltf(gltf_files[i])

