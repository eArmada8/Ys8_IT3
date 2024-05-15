# Tool to manipulate Ys VIII models in it3 format.  Replace mesh, material and texture sections of
# IT3 file with buffers previously exported.  Based on TwnKey's dumper (github.com/TwnKey/YsVIII_model_dump),
# with a TON of information from github.com/Kyuuhachi and github.com/uyjulian as well.
# Usage:  Run by itself without commandline arguments and it will read the mesh and texture section of
# every model it finds in the folder and replace them within the IT3 file.
#
# For command line options, run:
# /path/to/python3 ys3_it3_import_meshes.py --help
#
# Requires numpy, which can be installed by:
# /path/to/python3 -m pip install numpy
#
# Requires ys8_it3_export_assets.py, lib_falcompress.py and lib_fmtibvb.py, put in the same directory
#
# GitHub eArmada8/Ys8_IT3

try:
    import struct, os, numpy, shutil, json, sys, glob
    from ys8_it3_export_assets import *
    from lib_falcompress import *
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def swizzle (texture_data, dwHeight, dwWidth, block_size):
    morton_seq = [morton(x,8,8) for x in range(64)]
    output = bytearray(dwHeight * dwWidth // (16 // block_size))
    data_index = 0
    for y in range(((dwHeight // 4) + 7) // 8):
        for x in range(((dwWidth // 4) + 7) // 8):
            for t in range(64):
                y_offset = (y * 8) + (morton_seq[t] // 8)
                x_offset = (x * 8) + (morton_seq[t] % 8)
                if (x_offset < dwWidth // 4) and (y_offset < dwHeight // 4):
                    dest_index = block_size * (y_offset * (dwWidth // 4) + x_offset)
                    output[data_index:data_index+block_size] = texture_data[dest_index:dest_index+block_size]
                data_index += block_size
    return(output)

# ITP information from github.com/Aureole-Suite/Cradle, HUGE thank you to Kyuuhachi
def create_itp (texture_file, use_alpha = 1, compression_type = 3):
    if os.path.exists(texture_file):
        with open(texture_file, 'rb') as f:
            magic = f.read(4).decode("ASCII")
            if magic == 'DDS ':
                header = {}
                header['dwSize'], header['dwFlags'], header['dwHeight'], header['dwWidth'],\
                    header['dwPitchOrLinearSize'], header['dwDepth'], header['dwMipMapCount']\
                    = struct.unpack("<7I", f.read(28))
                f.seek(44,1) # Skipping 'dwReserved1'
                pixel_format = {}
                pixel_format['dwSize'], pixel_format['dwFlags'] = struct.unpack("<2I", f.read(8))
                pixel_format['dwFourCC'] = f.read(4).decode("ASCII")
                pixel_format['dwRGBBitCount'], pixel_format['dwRBitMask'], pixel_format['dwGBitMask'],\
                    pixel_format['dwBBitMask'], pixel_format['dwABitMask'] = struct.unpack("<5I", f.read(20))
                header['pixel_format'] = pixel_format
                header['dwCaps'], header['dwCaps2'], header['dwCaps3'], header['dwCaps4'] = struct.unpack("<4I", f.read(16))
                f.seek(4,1) # Skipping 'dwReserved2'
                if header['pixel_format']['dwFourCC'] == 'DX10':
                    dxt10_header = {}
                    dxt10_header['dxgiFormat'], dxt10_header['resourceDimension'],\
                    dxt10_header['miscFlag'], dxt10_header['arraySize'], dxt10_header['miscFlags2']\
                         = struct.unpack("<5I", f.read(20))
                    header['dxt10_header'] = dxt10_header
                itp_revision = 3
                pixel_format = 4 # PS4 Tile / Swizzle
                pixel_bit_format = 6 # Block Compression
                multi_plane = 0 # The only type known
                if header['pixel_format']['dwFourCC'] == 'DXT1':
                    block_size, base_format = 8, 6
                    use_alpha = 0 # BC1 has no alpha channels
                elif header['pixel_format']['dwFourCC'] == 'DXT5':
                    block_size, base_format = 16, 8
                elif (header['pixel_format']['dwFourCC'] == 'DX10' and header['dxt10_header']['dxgiFormat'] == 98):
                    block_size, base_format = 16, 10
                else:
                    return False # No support for anything but BC1, BC3, BC7 for now
                # IMIP 2nd value is MipMap type; 0 is none, 1 is type 1 and 2 is type 2 - I think we always use type 1.
                imip = b'IMIP' + struct.pack("<2I2HI", 12, 12, 1 if header['dwMipMapCount'] > 1 else 0, header['dwMipMapCount'] - 1, 0)
                ialp = b'IALP' + struct.pack("<2I2H", 8, 8, use_alpha, 0)
                idats = []
                for i in range(header['dwMipMapCount']):
                    tex_data = create_data_blocks(swizzle(f.read((header['dwHeight']>>i) * (header['dwWidth']>>i) // (16 // block_size)),\
                        header['dwHeight']>>i, header['dwWidth']>>i, block_size), compression_type)
                    idats.append(b'IDAT' + struct.pack("<2I2H", len(tex_data) + 8, 8, 0, i) + tex_data)
                idat = b''.join(idats)
                iend = b'IEND\x00\x00\x00\x00'
                data_size = 4 + 40 + len(imip) + len(ialp) + len(idat) + len(iend) #ITP\xff+IHDR+IMIP+IALP+IDAT+IEND - No support for IPAL/IHAS
                ihdr = b'IHDR' + struct.pack("<5I6HI", 32, 32, header['dwWidth'], header['dwHeight'], data_size,\
                    itp_revision, base_format, pixel_format, pixel_bit_format, compression_type, multi_plane, 0)
                itp_block = b'ITP\xff' + ihdr + imip + ialp + idat + iend
        return(itp_block)
    else:
        return(False)

def create_texi (texture, tex_folder, use_alpha = 1, compression_type = 3):
    itp_block = create_itp ("{0}/{1}".format(tex_folder, texture), use_alpha, compression_type)
    if not itp_block is False:
        texi_block = b'TEXI' + struct.pack("<I", len(itp_block)+36) + texture.split('.dds')[0].encode().ljust(36, b'\x00') +\
            itp_block
        return(texi_block)
    else:
        return(False)

# Acceptable block types include 'VPA9', 'VPAX' and 'VP11'
def create_vpax (submeshes, block_type = 'VPAX'):
    if block_type == 'VPA9':
        compression_type = 2
    else:
        compression_type = 3
    indices_data = bytes()
    vertices_data = bytes()
    count = 0
    # Initialize bounding box - I have no idea why this works, but it does.
    bbox = {'min_x': True, 'min_y': True, 'min_z': True, 'max_x': False, 'max_y': False, 'max_z': False}
    materials = []
    for i in range(len(submeshes)):
        if submeshes[i]['fmt']['stride'] == '160' and submeshes[i]['vb'][0]['SemanticName'] == 'POSITION':
            #Enforce correct index size for VPAX and VP11
            submeshes[i]['fmt']['format'] = {'VPA9': 'DXGI_FORMAT_R16_UINT', 'VPAX': 'DXGI_FORMAT_R16_UINT', 'VP11': 'DXGI_FORMAT_R32_UINT'}[block_type]
            if not submeshes[i]['material']['material_name'] in [x['material_name'] for x in materials]:
                materials.append(submeshes[i]['material'])
            bbox_min = [min(x[0] for x in submeshes[i]['vb'][0]['Buffer']), min(x[1] for x in submeshes[i]['vb'][0]['Buffer']),\
                min(x[2] for x in submeshes[i]['vb'][0]['Buffer']), 0.0]
            bbox_max = [max(x[0] for x in submeshes[i]['vb'][0]['Buffer']), max(x[1] for x in submeshes[i]['vb'][0]['Buffer']),\
                max(x[2] for x in submeshes[i]['vb'][0]['Buffer']), 0.0]
            bbox_mid = [(bbox_min[0]+bbox_max[0])/2, (bbox_min[1]+bbox_max[1])/2, (bbox_min[2]+bbox_max[2])/2, 0.0]
            bbox['min_x'] = min(bbox['min_x'], bbox_min[0])
            bbox['min_y'] = min(bbox['min_y'], bbox_min[1])
            bbox['min_z'] = min(bbox['min_z'], bbox_min[2])
            bbox['max_x'] = max(bbox['max_x'], bbox_max[0])
            bbox['max_y'] = max(bbox['max_y'], bbox_max[1])
            bbox['max_z'] = max(bbox['max_z'], bbox_max[2])
            # The 4 series of 16 integers are attr_format, attr_offset, attr_stride and attr_bitmask
            vpac_header = b'VPAC\x00\x00\x01\x00' + struct.pack("<4f", *bbox_mid) + struct.pack("<4f", *bbox_min) + struct.pack("<4f", *bbox_max) \
                + struct.pack("<4I", len(submeshes[i]['vb'][0]['Buffer']), len(submeshes[i]['vb'][0]['Buffer'])*160, 0xFFFF, 16) \
                + struct.pack("<16I", 1, 1, 1, 1, 2, 2, 3, 3, 1, 1, 1, 1, 3, 3, 3, 3) \
                + struct.pack("<16I", 0, 16, 32, 48, 64, 68, 72, 76, 80, 96, 112, 128, 144, 148, 152, 156) \
                + struct.pack("<16I", 16, 16, 16, 16, 4, 4, 4, 4, 16, 16, 16, 16, 4, 4, 4, 4) \
                + struct.pack("<16I", 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768) \
                + struct.pack("<9I", [x['material_name'] for x in materials].index(submeshes[i]['material']['material_name']), 0, 0, 0, 0, 0, 0, 0, 0)
            with io.BytesIO() as vb_stream:
                vb_stream.write(vpac_header)
                write_vb_stream(submeshes[i]['vb'], vb_stream, submeshes[i]['fmt'], e = '<', interleave = True)
                while vb_stream.tell() % 64 > 0:
                    vb_stream.write(b'\x00')
                vb_stream.seek(0,0)
                if block_type == 'VPA9':
                    vb_block = vb_stream.read()
                    vb_data = b''.join([create_data_blocks(vb_block[i*0x40000:(i+1)*0x40000], compression_type)\
                        for i in range((len(vb_block)-1)//0x40000+1)])
                else:
                    vb_data = create_data_blocks (vb_stream.read(), compression_type)
                vertices_data += struct.pack("<I", vb_stream.tell()) + vb_data
            with io.BytesIO() as ib_stream:
                write_ib_stream(submeshes[i]['ib'], ib_stream, submeshes[i]['fmt'], e = '<')
                ib_stream.seek(0,0)
                if block_type == 'VPA9':
                    ib_block = ib_stream.read()
                    ib_data = b''.join([create_data_blocks(ib_block[i*0x40000:(i+1)*0x40000], compression_type)\
                        for i in range((len(ib_block)-1)//0x40000+1)])
                else:
                    ib_data = create_data_blocks (ib_stream.read(), compression_type)
                indices_data += struct.pack("<I", ib_stream.tell()//{'VPA9': 2, 'VPAX': 2, 'VP11': 4}[block_type]) + ib_data
            count += 1
    vpax_stream = struct.pack("<I", count) + vertices_data + indices_data
    vpax_block = block_type.encode() + struct.pack("<I", len(vpax_stream)) + vpax_stream
    bbox_array = [[bbox['min_x'], bbox['min_y'], bbox['min_z'], 1.0], [bbox['max_x'] ,bbox['max_y'], bbox['max_z'], 1.0],\
        [(bbox['min_x'] + bbox['max_x'])/2, (bbox['min_y'] + bbox['max_y'])/2, (bbox['min_z'] + bbox['max_z'])/2,\
        numpy.linalg.norm(numpy.array([bbox['min_x'], bbox['min_y'], bbox['min_z']]) - numpy.array([bbox['max_x'], bbox['max_y'], bbox['max_z']]))/2.0]]
    bbox_block = b'BBOX' + struct.pack("<I", 48) + struct.pack("<12f", *[x for y in bbox_array for x in y])
    return(vpax_block, bbox_block, materials)

def create_mat6 (materials, compression_type = 3):
    compressed_data = struct.pack("<I", len(materials))
    for i in range(len(materials)):
        part1 = struct.pack("<7I", *materials[i]['unk0']) \
            + struct.pack("<3I", len(materials[i]['parameters']), len(materials[i]['textures'])*16, len(materials[i]['textures'])) \
            + b''.join([struct.pack("<4f", *x) for x in materials[i]['parameters']]) \
            + b''.join([struct.pack("<4I", *x['flags']) for x in materials[i]['textures']])
        part1 += b''.join([b'\x00' for _ in range(64 - ((len(part1) + 12) % 64))])
        part2 = struct.pack("<I", 64) + materials[i]['material_name'].encode().ljust(64, b'\x00') \
            + struct.pack("<I", 32) + b''.join([x['name'].encode().ljust(32, b'\x00') for x in materials[i]['textures']])
        block = b'MATM' + struct.pack("<2I", materials[i]['MATM_flags'], len(part1)+12) + part1 \
            + b'MATE' + struct.pack("<2I", materials[i]['MATE_flags'], len(part2)+12) + part2
        compressed_data += struct.pack("<I", len(block)) + create_data_blocks(block, compression_type) 
    mat6_block = b'MAT6' + struct.pack("<I", len(compressed_data)) + compressed_data
    return(mat6_block)

# .bonemap files are in the exact same format as .vgmap files.
def create_bon3 (bonemap, node_name, compression_type = 3):
    true_map = list(bonemap.keys())[1:] #Ignore the first entry, as the map starts at 1
    bon3_block_data = struct.pack("<I", 256) + node_name.encode().ljust(64, b'\x00') \
        + struct.pack("<I", len(true_map)) \
        + create_data_blocks(b''.join([x.encode().ljust(64, b'\x00') for x in true_map]), compression_type) \
        + create_data_blocks(b'', compression_type) + create_data_blocks(b'', compression_type)
    return(b'BON3' + struct.pack("<I", len(bon3_block_data)) + bon3_block_data)

def create_rty2 (rty2_data):
    rty2_block_data = struct.pack("<I", rty2_data['material_variant']) \
        + struct.pack("<B", rty2_data['unknown']) \
        + struct.pack("<3f", *rty2_data['v0'])
    return(b'RTY2' + struct.pack("<I", len(rty2_block_data)) + rty2_block_data)

def rapid_parse_it3 (f):
    file_length = f.seek(0,2)
    f.seek(0,0)
    contents = {}
    info_section = ''
    while f.tell() < file_length:
        section_info = {}
        section_info["type"] = f.read(4).decode('ASCII')
        section_info["size"], = struct.unpack("<I",f.read(4))
        section_info["section_start_offset"] = f.tell()
        if section_info["type"] == 'INFO':
            if info_section != '':
                contents[info_section]['length'] = section_info["section_start_offset"] - 8 - contents[info_section]['offset']
            section_info["data"] = parse_info_block(f)
            info_section = section_info["data"]["name"]
            contents[section_info["data"]["name"]] = {'offset': section_info["section_start_offset"]-8, 'contents': []}
        else:
            contents[info_section]['contents'].append(section_info["type"])
        f.seek((section_info["section_start_offset"] + section_info["size"]), 0) # Move forward to the next section
    contents[info_section]['length'] = f.tell() - contents[info_section]['offset']
    return(contents)

def return_rty2_material(f, it3_section):
    f.seek(it3_section['offset'])
    while f.tell() < it3_section['offset'] + it3_section['length']:
        magic = f.read(4).decode("ASCII")
        size, = struct.unpack("<I", f.read(4))
        if magic == 'RTY2':
            rty_data = parse_rty2_block(f)
            return rty_data["material_variant"]
        else:
            f.seek(size,1)
    return -1

def process_it3 (it3_filename, import_noskel = False):
    with open(it3_filename,"rb") as f:
        it3_contents = rapid_parse_it3 (f)
        # Will read data from JSON file, or load original data from the mdl file if JSON is missing
        try:
            material_struct = read_struct_from_json(it3_filename[:-4] + '/materials_metadata.json')
        except:
            material_struct = {}
            print("{0}/materials_metadata.json missing or unreadable, reading data from {0}.it3 instead...".format(it3_filename[:-4]))
            to_process_mat6 = [x for x in it3_contents if 'MAT6' in it3_contents[x]['contents']]
            for section in to_process_mat6:
                mat6 = []
                rty2 = {}
                f.seek(it3_contents[section]['offset'])
                while f.tell() < it3_contents[section]['offset']+it3_contents[section]['length']:
                    section_info = {}
                    section_info["type"] = f.read(4).decode('ASCII')
                    section_info["size"], = struct.unpack("<I",f.read(4))
                    if (section_info["type"] == 'MAT6'):
                        mat6 = parse_mat6_block(f)
                    elif (section_info["type"] == 'RTY2'):
                        rty2 = parse_rty2_block(f)
                    else:
                        f.seek(section_info["size"],1)
                mats = {}
                for i in range(len(mat6)):
                    material_name = mat6[i].pop('material_name')
                    mats[material_name] = mat6[i]
                material_struct[section] = {'rty2_shader_assignment': rty2, 'material_parameters': mats}
        to_process_tex = [x for x in it3_contents if 'TEXI' in it3_contents[x]['contents']] #TEXF someday?
        to_process_vp = [x for x in it3_contents if any(y in it3_contents[x]['contents'] for y in ['VPA9','VPAX','VP11'])]
        if import_noskel == False:
            to_process_vp = [x for x in to_process_vp if return_rty2_material(f, it3_contents[x]) != 8]
        new_it3 = bytes()
        compression_type = 2 # Set a default; I don't think there are any IT3s without VPA sections but just in case
        for section in it3_contents:
            # VPA blocks in TEX sections will not be altered - may change if needed in future
            if section in to_process_vp:
                if 'VP11' in it3_contents[section]['contents']:
                    block_type = 'VP11'
                    compression_type = 3
                elif 'VPAX' in it3_contents[section]['contents']:
                    block_type = 'VPAX'
                    compression_type = 3
                else:
                    block_type = 'VPA9'
                    compression_type = 2
                f.seek(it3_contents[section]['offset'])
                # Build VPAX/VP11, BBOX, MAT6
                submeshfiles = [x[:-4] for x in glob.glob(it3_filename[:-4] + '/meshes/{}_*.fmt'.format(section))]
                submeshes = []
                for j in range(len(submeshfiles)):
                    print("Reading submesh {0}...".format(submeshfiles[j]))
                    try:
                        fmt = read_fmt(submeshfiles[j] + '.fmt')
                        ib = read_ib(submeshfiles[j] + '.ib', fmt)
                        ib = [[x[0],x[2],x[1]] for x in ib] # Swap DirectX triangles back to OpenGL
                        vb = read_vb(submeshfiles[j] + '.vb', fmt)
                        vgmap = read_struct_from_json(submeshfiles[j] + '.vgmap')
                        material_file = read_struct_from_json(submeshfiles[j] + '.material')
                        material_name = material_file['material_name']
                        try:
                            material = material_struct[section]['material_parameters'][material_name]
                            material['material_name'] = material_name
                        except KeyError:
                            print("KeyError: Attempted to add material {0}, but it does not exist in material_metadata.json!".format(material_name))
                            if 'unk0' in material_file: # Backwards-compatibility with older metadata format
                                print("Pre-v1.1.0 version metadata detected, importing...")
                                material = material_file
                            else:
                                input("Press Enter to abort.")
                                raise
                        submeshes.append({'fmt': fmt, 'ib': ib, 'vb': vb, 'vgmap': vgmap, 'material': material})
                    except FileNotFoundError:
                        print("Submesh {0} not found, skipping...".format(submeshfiles[j]))
                        continue
                if len(submeshes) == 0:
                    # Insert an empty mesh
                    fmt = make_fmt(0xFFFF, {'VPA9':1, 'VPAX':1, 'VP11':2}[block_type])
                    submeshes.append({'fmt': fmt, 'ib': [],\
                    'vb': read_vb_stream(b''.join([b'\x00' for _ in range(480)]), fmt),\
                    'vgmap': {section:0},\
                    'material': {"material_name": "", "MATM_flags": 65793, "MATE_flags": 65793,\
                        "unk0": [28,0,0,0,0,0,0], "parameters": [], "textures": []}})
                vp_block, bbox_block, materials = create_vpax(submeshes, block_type = block_type)
                mat6_block = create_mat6(materials, compression_type)
                custom_bonemap = False
                if os.path.exists(it3_filename[:-4] + '/meshes/{}.bonemap'.format(section)):
                    bonemap = read_struct_from_json(it3_filename[:-4] + '/meshes/{}.bonemap'.format(section))
                    bon3_block = create_bon3(bonemap, section, compression_type)
                    custom_bonemap = True
                custom_rty2 = False
                if 'rty2_shader_assignment' in material_struct[section]:
                    rty2_block = create_rty2(material_struct[section]['rty2_shader_assignment'])
                    custom_rty2 = True
                while f.tell() < it3_contents[section]['offset']+it3_contents[section]['length']:
                    section_info = {}
                    section_info["type"] = f.read(4).decode('ASCII')
                    section_info["size"], = struct.unpack("<I",f.read(4))
                    if (section_info["type"] in ['VPA9', 'VPAX', 'VP11']):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3 += vp_block
                    elif (section_info["type"] == 'BBOX'):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3 += bbox_block
                    elif (section_info["type"] == 'MAT6'):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3 += mat6_block
                    elif (section_info["type"] == 'BON3') and custom_bonemap == True:
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3 += bon3_block
                    elif (section_info["type"] == 'RTY2') and custom_rty2 == True:
                        f.seek(section_info["size"],1)
                        new_it3 += rty2_block
                    elif (section_info["type"] == 'TEXI'):
                        f.seek(section_info["size"],1)
                    else:
                        new_it3 += section_info["type"].encode() + struct.pack("<I", section_info["size"]) \
                            + f.read(section_info["size"])
            elif section in to_process_tex: 
                f.seek(it3_contents[section]['offset'])
                while f.tell() < it3_contents[section]['offset']+it3_contents[section]['length']:
                    section_info = {}
                    section_info["type"] = f.read(4).decode('ASCII')
                    section_info["size"], = struct.unpack("<I",f.read(4))
                    if (section_info["type"] == 'TEXI'):
                        f.seek(section_info["size"],1)
                    else:
                        new_it3 += section_info["type"].encode() + struct.pack("<I", section_info["size"]) \
                            + f.read(section_info["size"])
            else:
                f.seek(it3_contents[section]['offset'])
                new_it3 += f.read(it3_contents[section]['length'])
        # Append all textures to the end of the IT3 file
        if os.path.exists(it3_filename[:-4] + '/textures'):
            textures = [os.path.basename(x) for x in glob.glob(it3_filename[:-4] + '/textures/*.dds')]
            alpha_data = {}
            if os.path.exists(it3_filename[:-4] + '/textures/__alpha_data.json'):
                with open(it3_filename[:-4] + '/textures/__alpha_data.json','rb') as f2:
                    alpha_data = json.loads(f2.read())
            for texture in textures:
                use_alpha = alpha_data[texture[:-4]] if texture[:-4] in alpha_data else 0
                new_itp = create_texi (texture, it3_filename[:-4] + '/textures', use_alpha, compression_type)
                if new_itp != False:
                    print("Importing {0}.".format(texture))
                    new_it3 += new_itp
                else:
                    print("Unable to import {}.".format(texture))
        # Instead of overwriting backups, it will just tag a number onto the end
        backup_suffix = ''
        if os.path.exists(it3_filename + '.bak' + backup_suffix):
            backup_suffix = '1'
            if os.path.exists(it3_filename + '.bak' + backup_suffix):
                while os.path.exists(it3_filename + '.bak' + backup_suffix):
                    backup_suffix = str(int(backup_suffix) + 1)
            shutil.copy2(it3_filename, it3_filename + '.bak' + backup_suffix)
        else:
            shutil.copy2(it3_filename, it3_filename + '.bak')
        with open(it3_filename,'wb') as f2:
            f2.write(new_it3)

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
        parser.add_argument('-n', '--import_noskel', help="Import physics meshes (RTY2 material == 8) from ib/vb instead of it3", action="store_true")
        parser.add_argument('it3_filename', help="Name of it3 file to import into (required).")
        args = parser.parse_args()
        if os.path.exists(args.it3_filename) and args.it3_filename[-4:].lower() == '.it3':
            process_it3(args.it3_filename, import_noskel = args.import_noskel)
    else:
        it3_files = glob.glob('*.it3')
        for i in range(len(it3_files)):
            process_it3(it3_files[i])
