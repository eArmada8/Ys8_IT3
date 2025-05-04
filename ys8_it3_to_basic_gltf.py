# Tool to convert Ys VIII models in it3 format to glTF.  Not as useful as TwnKey's
# script, but is meant to be used as a research tool.
#
# Usage:  Run by itself without commandline arguments and it will convert it3 files that it finds.
#
# For command line options (including option to dump vertices), run:
# /path/to/python3 ys8_it3_to_basic_gltf.py --help
#
# Requires numpy and pyquaternion.
# These can be installed by:
# /path/to/python3 -m pip install numpy pyquaternion
#
# Requires ys8_it3_export_assets.py and lib_fmtibvb.py, put in the same directory
#
# GitHub eArmada8/Ys8_IT3

try:
    import io, struct, sys, os, glob, numpy, json
    from pyquaternion import Quaternion
    from ys8_it3_export_assets import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def obtain_skeleton_data (it3_contents, it3_filename, flip_axis = True):
    nodes = [x for x in it3_contents if x['type'] == 'INFO']
    node_dict = {}
    if len(set([x['data']['name'] for x in nodes])) != len(nodes):
        return('Error: duplicate INFO names')
    node_dict = dict([(nodes[i]['data']['name'], i+1) for i in range(len(nodes))]) #root starts at 1
    chid_dict = dict([(x['info_name'], x['data']['children']) for x in it3_contents if x['type'] == 'CHID'])
    # Insert an empty node at the origin, since root starts at 1.  Flip axis is default
    if flip_axis: # Change Y up / -X forward to Z up / Y forward
        base_node = [[1.0,0.0,0.0,0.0],[0.0,0.0,-1.0,0.0],[0.0,1.0,0.0,0.0],[0.0,0.0,0.0,1.0]]
    else:
        base_node = [[1.0,0.0,0.0,0.0],[0.0,1.0,0.0,0.0],[0.0,0.0,1.0,0.0],[0.0,0.0,0.0,1.0]]
    node_blocks = [{'id': 0, 'name': it3_filename[:-4], 'rel_matrix': base_node, 'children':[1]}]
    for i in range(len(nodes)):
        node_block = {}
        node_block['id'] = node_dict[nodes[i]['data']['name']]
        node_block['name'] = nodes[i]['data']['name']
        node_block['rel_matrix'] = nodes[i]['data']['matrix']
        if node_block['name'] in chid_dict:
            node_block['children'] = [node_dict[x] for x in chid_dict[node_block['name']]]
        else:
            node_block['children'] = []
        node_blocks.append(node_block)
    for i in range(len(node_blocks)):
        if i == 0:
            node_blocks[i]['parentID'] = -1
            node_blocks[i]['matrix'] = node_blocks[i]['rel_matrix']
        else:
            node_blocks[i]['parentID'] = [x['id'] for x in node_blocks if i in x['children']][0]
            node_blocks[i]['matrix'] = numpy.dot(numpy.array(node_blocks[i]['rel_matrix']),\
                numpy.array(node_blocks[node_blocks[i]['parentID']]['matrix'])).tolist()
    return(node_blocks)

# This only handles formats compatible with Ys8 MDL (Float, UINT, SNORM, UNORM)
def convert_format_for_gltf(dxgi_format):
    dxgi_format = dxgi_format.split('DXGI_FORMAT_')[-1]
    dxgi_format_split = dxgi_format.split('_')
    if len(dxgi_format_split) == 2:
        numtype = dxgi_format_split[1]
        vec_format = re.findall("[0-9]+",dxgi_format_split[0])
        vec_bits = int(vec_format[0])
        vec_elements = len(vec_format)
        accessor_type = ["SCALAR", "VEC2", "VEC3", "VEC4"][vec_elements-1]
        if numtype in ['SNORM', 'UNORM']:
            numtype = 'FLOAT'
        if numtype == 'FLOAT':
            componentType = 5126
            componentStride = vec_elements * 4
            dxgi_format = ['R32_FLOAT', 'R32G32_FLOAT', 'R32G32B32_FLOAT', 'R32G32B32A32_FLOAT'][vec_elements-1]
        elif numtype == 'UINT': # Bit-shifting 8, 16 and 32 into 0, 1 and 2
            componentType = [5121, 5123, 5125][vec_bits >> 4]
            componentStride = vec_elements * [1, 2, 4][vec_bits >> 4]
        return({'format': dxgi_format, 'componentType': componentType,\
            'componentStride': componentStride, 'accessor_type': accessor_type})
    else:
        return(False)

def convert_submesh_for_gltf(submesh, flip_axis = True):
    new_fmt = {'stride': '0', 'topology': submesh['fmt']['topology'], 'format': '', 'elements': []}
    new_ib = submesh['ib']
    new_vb = []
    stride = 0
    element_counter = 0
    new_semantics = {'BLENDWEIGHT': 'WEIGHTS', 'BLENDWEIGHTS': 'WEIGHTS', 'BLENDINDICES': 'JOINTS'}
    need_index = ['WEIGHTS', 'JOINTS', 'COLOR', 'TEXCOORD']
    need_fewer_values = {'POSITION': 3, 'NORMAL': 3, 'TEXCOORD': 2}
    has_axes = ['POSITION', 'NORMAL', 'TANGENT']
    normalize = ['NORMAL']
    truncated_dxgi = {2: 'R32G32_FLOAT', 3: 'R32G32B32_FLOAT'}
    for i in range(len(submesh['fmt']['elements'])):
        if not submesh['fmt']['elements'][i]['SemanticName'] == 'UNKNOWN':
            new_element = {'id': '{0}'.format(element_counter), 'SemanticName': '',\
                'SemanticIndex': submesh['fmt']['elements'][i]['SemanticIndex'],\
                'Format': '', 'InputSlot': '0', 'AlignedByteOffset': '',\
                'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}
            if submesh['fmt']['elements'][i]['SemanticName'] in new_semantics.keys():
                new_element['SemanticName'] = new_semantics[submesh['fmt']['elements'][i]['SemanticName']]
            else:
                new_element['SemanticName'] = submesh['fmt']['elements'][i]['SemanticName']
            if new_element['SemanticName'] in need_fewer_values.keys():
                dxgi_format = truncated_dxgi[need_fewer_values[new_element['SemanticName']]]
                buffer = [x[0:need_fewer_values[new_element['SemanticName']]] for x in submesh['vb'][i]["Buffer"]]
                if new_element['SemanticName'] in has_axes and flip_axis == True:
                    buffer = [[x[0],x[2],-x[1]] for x in buffer]
                if new_element['SemanticName'] in normalize:
                    buffer = [(x/numpy.linalg.norm(x)).tolist() for x in buffer]
                new_vb.append({"SemanticName": submesh['vb'][i]["SemanticName"],\
                    "SemanticIndex": submesh['vb'][i]["SemanticIndex"],\
                    "Buffer": buffer})
            else:
                dxgi_format = submesh['fmt']['elements'][i]['Format']
                new_vb.append(submesh['vb'][i])
            if new_element['SemanticName'] == 'WEIGHTS':
                weight_sums = [sum(x) for x in new_vb[-1]["Buffer"]]
                new_vb[-1]["Buffer"] = [[x/weight_sums[i] if weight_sums[i] > 0.0 else x for x in new_vb[-1]["Buffer"][i]] for i in range(len(new_vb[-1]["Buffer"]))]
            new_info = convert_format_for_gltf(dxgi_format)
            new_element['Format'] = new_info['format']
            if new_element['SemanticName'] in need_index:
                new_element['SemanticName'] = new_element['SemanticName'] + '_' + new_element['SemanticIndex']
            new_element['AlignedByteOffset'] = stride
            new_element['componentType'] = new_info['componentType']
            new_element['componentStride'] = new_info['componentStride']
            new_element['accessor_type'] = new_info['accessor_type']
            new_fmt['elements'].append(new_element)
            stride += new_info['componentStride']
            element_counter += 1
    index_fmt = convert_format_for_gltf(submesh['fmt']['format'])
    new_fmt['format'] = index_fmt['format']
    new_fmt['componentType'] = index_fmt['componentType']
    new_fmt['componentStride'] = index_fmt['componentStride']
    new_fmt['accessor_type'] = index_fmt['accessor_type']
    new_fmt['stride'] = stride
    return({'fmt': new_fmt, 'ib': new_ib, 'vb': new_vb})

def local_to_global_bone_indices(mesh_index, mesh_struct, skel_struct):
    local_node_dict = {}
    for i in range(len(mesh_struct[mesh_index]["node_list"])):
        local_node_dict[i] = mesh_struct[mesh_index]["node_list"][i]
    global_node_dict = {}
    for key in local_node_dict:
        global_node_dict[key] = [x for x in skel_struct if x['name'] == local_node_dict[key]][0]['id']
    return(global_node_dict)

def generate_materials(gltf_data, it3_contents):
    mat_blocks = [i for i in range(len(it3_contents)) if it3_contents[i]['type'] in ['MAT4','MAT6']]
    images = sorted(list(set([x['name'] for y in [x['textures'] for y in [x for y in mat_blocks for x in [it3_contents[y]['data']]] for x in y] for x in y])))
    gltf_data['images'] = [{'uri':'textures/{}.png'.format(x)} for x in images]
    for i in range(len(mat_blocks)):
        info_name = it3_contents[mat_blocks[i]]['info_name']
        for j in range(len(it3_contents[mat_blocks[i]]['data'])):
            add_material = False
            material = {}
            material['name'] = it3_contents[mat_blocks[i]]['data'][j]['material_name']
            if it3_contents[mat_blocks[i]]['type'] == 'MAT6':
                for k in range(len(it3_contents[mat_blocks[i]]['data'][j]['textures'])):
                    add_texture = False
                    sampler = { 'wrapS': {0:10497,1:33071,2:33648}[it3_contents[mat_blocks[i]]['data'][j]['textures'][k]['flags'][2]],\
                        'wrapT': {0:10497,1:33071,2:33648}[it3_contents[mat_blocks[i]]['data'][j]['textures'][k]['flags'][3]] }
                    texture = { 'source': images.index(it3_contents[mat_blocks[i]]['data'][j]['textures'][k]['name']), 'sampler': len(gltf_data['samplers']) }
                    if k == 0:
                        material['pbrMetallicRoughness']= { 'baseColorTexture' : { 'index' : len(gltf_data['textures']), 'texCoord': 0 },\
                            'metallicFactor' : 0.0, 'roughnessFactor' : 1.0 }
                        add_texture = True
                    elif it3_contents[mat_blocks[i]]['data'][j]['textures'][k]['name'] == it3_contents[mat_blocks[i]]['data'][j]['textures'][0]['name']+'n':
                        material['normalTexture'] =  { 'index' : len(gltf_data['textures']), 'texCoord': 0 }
                        add_texture = True
                    if add_texture == True:
                        add_material = True
                        gltf_data['samplers'].append(sampler)
                        gltf_data['textures'].append(texture)
            else: # MAT4
                if len(it3_contents[mat_blocks[i]]['data'][j]['textures']) > 0:
                    sampler = { 'wrapS': 10497, 'wrapT': 10497 } # Figure this out later
                    texture = { 'source': images.index(it3_contents[mat_blocks[i]]['data'][j]['textures'][0]['name']), 'sampler': len(gltf_data['samplers']) }
                    material['pbrMetallicRoughness']= { 'baseColorTexture' : { 'index' : len(gltf_data['textures']), 'texCoord': 0 },\
                        'metallicFactor' : 0.0, 'roughnessFactor' : 1.0 }
                    add_material = True
                    gltf_data['samplers'].append(sampler)
                    gltf_data['textures'].append(texture)
            if add_material == True:
                material['alphaMode'] = 'MASK' # Not optimal since clearly some models use some form of alpha blending, but this will have to do.
                gltf_data['materials'].append(material)
    return(gltf_data)

def write_glTF(filename, it3_contents, mesh_struct, skel_struct, flip_axis = True, render_non_skel_meshes = False):
    gltf_data = {}
    gltf_data['asset'] = { 'version': '2.0' }
    gltf_data['accessors'] = []
    gltf_data['bufferViews'] = []
    gltf_data['buffers'] = []
    gltf_data['meshes'] = []
    gltf_data['materials'] = []
    gltf_data['nodes'] = []
    gltf_data['samplers'] = []
    gltf_data['scenes'] = [{}]
    gltf_data['scenes'][0]['nodes'] = [0]
    gltf_data['scene'] = 0
    gltf_data['skins'] = []
    gltf_data['textures'] = []
    giant_buffer = bytes()
    mesh_nodes = []
    buffer_view = 0
    gltf_data = generate_materials(gltf_data, it3_contents)
    missing_textures = [x['uri'] for x in gltf_data['images'] if not os.path.exists(x['uri'])]
    if len(missing_textures) > 0:
        print("Warning:  The following textures were not found:")
        for texture in missing_textures:
            print("{}".format(texture))
    g_material_dict = {gltf_data['materials'][i]['name']:i for i in range(len(gltf_data['materials']))}
    vpax_blocks = [i for i in range(len(it3_contents)) if it3_contents[i]['type'] in ['VPA7', 'VPA8', 'VPA9', 'VPAX', 'VP11']]
    material_dict = {}
    for i in range(len(vpax_blocks)):
        mat_block = [j for j in range(len(it3_contents)) if it3_contents[j]['type'] in ['MAT4', 'MAT6'] and it3_contents[j]['info_name'] == it3_contents[vpax_blocks[i]]['info_name']][0]
        local_mat_index = it3_contents[mat_block]
        material_dict[it3_contents[vpax_blocks[i]]['info_name']] \
            = [g_material_dict[it3_contents[mat_block]['data'][x['header']['material_id']]['material_name']] for x in it3_contents[vpax_blocks[i]]['data'] \
                if x['header']['material_id'] < len(it3_contents[mat_block]['data']) \
                and it3_contents[mat_block]['data'][x['header']['material_id']]['material_name'] in g_material_dict]
    for i in range(len(skel_struct)):
        node = {'children': skel_struct[i]['children'], 'name': skel_struct[i]['name'],\
            'matrix': [x for y in numpy.array(skel_struct[i]['rel_matrix']).tolist() for x in y]}
        gltf_data['nodes'].append(node)
    for i in range(len(gltf_data['nodes'])):
        if len(gltf_data['nodes'][i]['children']) == 0:
            del(gltf_data['nodes'][i]['children'])
    for i in range(len(mesh_struct)): # Mesh
        mesh_rty2 = [j for j in range(len(it3_contents)) if it3_contents[j]['type'] == 'RTY2' and it3_contents[j]['info_name'] == it3_contents[vpax_blocks[i]]['info_name']][0]
        rty2_setting = it3_contents[mesh_rty2]['data']['material_variant']
        primitives = []
        mesh_node = [j for j in range(len(gltf_data['nodes']))\
            if gltf_data['nodes'][j]['name'] == mesh_struct[i]["name"]][0]
        if rty2_setting != 8 or render_non_skel_meshes == True: # Node list should always have at least one node, even non-skeletal
            for j in range(len(mesh_struct[i]["meshes"])): # Submesh
                print("Processing {0} submesh {1}...".format(mesh_struct[i]["name"], j))
                submesh = convert_submesh_for_gltf(mesh_struct[i]["meshes"][j], flip_axis = flip_axis)
                gltf_fmt = submesh['fmt']
                primitive = {"attributes":{}}
                vb_stream = io.BytesIO()
                write_vb_stream(submesh['vb'], vb_stream, gltf_fmt, e='<', interleave = False)
                block_offset = len(giant_buffer)
                for element in range(len(gltf_fmt['elements'])):
                    primitive["attributes"][gltf_fmt['elements'][element]['SemanticName']]\
                        = len(gltf_data['accessors'])
                    gltf_data['accessors'].append({"bufferView" : buffer_view,\
                        "componentType": gltf_fmt['elements'][element]['componentType'],\
                        "count": len(submesh['vb'][element]['Buffer']),\
                        "type": gltf_fmt['elements'][element]['accessor_type']})
                    if gltf_fmt['elements'][element]['SemanticName'] == 'POSITION':
                        gltf_data['accessors'][-1]['max'] =\
                            [max([x[0] for x in submesh['vb'][element]['Buffer']]),\
                             max([x[1] for x in submesh['vb'][element]['Buffer']]),\
                             max([x[2] for x in submesh['vb'][element]['Buffer']])]
                        gltf_data['accessors'][-1]['min'] =\
                            [min([x[0] for x in submesh['vb'][element]['Buffer']]),\
                             min([x[1] for x in submesh['vb'][element]['Buffer']]),\
                             min([x[2] for x in submesh['vb'][element]['Buffer']])]
                    gltf_data['bufferViews'].append({"buffer": 0,\
                        "byteOffset": block_offset,\
                        "byteLength": len(submesh['vb'][element]['Buffer']) *\
                        gltf_fmt['elements'][element]['componentStride'],\
                        "target" : 34962})
                    block_offset += len(submesh['vb'][element]['Buffer']) *\
                        gltf_fmt['elements'][element]['componentStride']
                    buffer_view += 1
                vb_stream.seek(0)
                giant_buffer += vb_stream.read()
                vb_stream.close()
                del(vb_stream)
                ib_stream = io.BytesIO()
                write_ib_stream(submesh['ib'], ib_stream, gltf_fmt, e='<')
                # IB is 16-bit so can be misaligned, unlike VB (which only has 32-, 64- and 128-bit types in Kuro)
                while (ib_stream.tell() % 4) > 0:
                    ib_stream.write(b'\x00')
                primitive["indices"] = len(gltf_data['accessors'])
                gltf_data['accessors'].append({"bufferView" : buffer_view,\
                    "componentType": gltf_fmt['componentType'],\
                    "count": len([index for triangle in submesh['ib'] for index in triangle]),\
                    "type": gltf_fmt['accessor_type']})
                gltf_data['bufferViews'].append({"buffer": 0,\
                    "byteOffset": len(giant_buffer),\
                    "byteLength": ib_stream.tell(),\
                    "target" : 34963})
                buffer_view += 1
                ib_stream.seek(0)
                giant_buffer += ib_stream.read()
                ib_stream.close()
                del(ib_stream)
                primitive["mode"] = 4 #TRIANGLES
                if mesh_struct[i]["name"] in material_dict and len(material_dict[mesh_struct[i]["name"]]) > j:
                    primitive["material"] = material_dict[mesh_struct[i]["name"]][j]
                primitives.append(primitive)
                del(submesh)
            gltf_data['nodes'][mesh_node]['mesh'] = len(gltf_data['meshes'])
            gltf_data['meshes'].append({"primitives": primitives, "name": mesh_struct[i]["name"]})
        if len(mesh_struct[i]["node_list"]) > 0:
            global_node_dict = local_to_global_bone_indices(i, mesh_struct, skel_struct)
            gltf_data['nodes'][mesh_node]['skin'] = len(gltf_data['skins'])
            inv_mtx_buffer = bytes()
            for k in global_node_dict:
                inv_bind_mtx = [num for row in numpy.linalg.inv(numpy.array(skel_struct[global_node_dict[k]]['matrix'])).tolist() for num in row]
                inv_bind_mtx = [round(x,15) for x in inv_bind_mtx]
                inv_mtx_buffer += struct.pack("<16f", *inv_bind_mtx)
            gltf_data['skins'].append({"inverseBindMatrices": len(gltf_data['accessors']), "joints": list(global_node_dict.values())})
            gltf_data['accessors'].append({"bufferView" : buffer_view,\
                "componentType": 5126,\
                "count": len(global_node_dict),\
                "type": "MAT4"})
            gltf_data['bufferViews'].append({"buffer": 0,\
                "byteOffset": len(giant_buffer),\
                "byteLength": len(inv_mtx_buffer)})
            buffer_view += 1
            giant_buffer += inv_mtx_buffer
    gltf_data['scenes'][0]['nodes'].extend(mesh_nodes)
    gltf_data['buffers'].append({"byteLength": len(giant_buffer), "uri": filename[:-4]+'.bin'})
    with open(filename[:-4]+'.bin', 'wb') as f:
        f.write(giant_buffer)
    with open(filename[:-4]+'.gltf', 'wb') as f:
        f.write(json.dumps(gltf_data, indent=4).encode("utf-8"))

def process_it3 (it3_filename, flip_axis = True, render_non_skel_meshes = False, overwrite = False):
    print("Processing {0}...".format(it3_filename))
    with open(it3_filename, "rb") as f:
        it3_contents = parse_it3(f)
        it3_contents, mesh_struct = obtain_mesh_data(f, it3_contents, it3_filename, preserve_gl_order = False, trim_for_gpu = True)
    skel_struct = obtain_skeleton_data(it3_contents, it3_filename, flip_axis = flip_axis)
    if os.path.exists(it3_filename[:-4] + '.gltf') and (overwrite == False):
        if str(input(it3_filename[:-4] + ".gltf exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(it3_filename[:-4] + '.gltf'):
        write_glTF(it3_filename, it3_contents, mesh_struct, skel_struct, flip_axis = flip_axis,\
            render_non_skel_meshes = render_non_skel_meshes)

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
        parser.add_argument('-n', '--no_axis_flip', help="Keep Y up", action="store_false")
        parser.add_argument('-r', '--render_no_skel', help="Render meshes without weights", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('it3_filename', help="Name of it3 file to process.")
        args = parser.parse_args()
        if os.path.exists(args.it3_filename) and args.it3_filename[-4:].lower() == '.it3':
            process_it3(args.it3_filename, flip_axis = args.no_axis_flip,\
                render_non_skel_meshes = args.render_no_skel, overwrite = args.overwrite)
    else:
        it3_files = glob.glob('*.it3')
        for i in range(len(it3_files)):
            process_it3(it3_files[i])
