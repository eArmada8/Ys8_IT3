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
    import struct, io, os, math, numpy, re, shutil, json, sys, glob, multiprocessing
    from ys8_it3_export_assets import *
    from lib_falcompress import *
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def swizzle (texture_data, dwHeight, dwWidth, block_size):
    if block_size in [8,16]: # Block compression
        gridWidth, gridHeight = math.ceil(dwWidth/4), math.ceil(dwHeight/4)
    else: # Uncompressed ARGB
        gridWidth, gridHeight = dwWidth, dwHeight
    morton_seq = [morton(x,8,8) for x in range(64)]
    output = bytearray(gridWidth * gridHeight * block_size)
    data_index = 0
    for y in range((gridHeight + 7) // 8):
        for x in range((gridWidth + 7) // 8):
            for t in range(64):
                y_offset = (y * 8) + (morton_seq[t] // 8)
                x_offset = (x * 8) + (morton_seq[t] % 8)
                if (x_offset < gridWidth) and (y_offset < gridHeight):
                    dest_index = block_size * (y_offset * gridWidth + x_offset)
                    output[data_index:data_index+block_size] = texture_data[dest_index:dest_index+block_size]
                    data_index += block_size
    return(output)

# ITP v3 information from github.com/Aureole-Suite/Cradle, HUGE thank you to Kyuuhachi
def create_itp (texture_file, use_alpha = 1, compression_type = 3):
    if os.path.exists(texture_file):
        itp_block = False
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
                pixel_tile_format = 4 # PS4 Tile / Swizzle
                multi_plane = 0 # The only type known
                dwRGBBitCount, pixelflags = pixel_format['dwRGBBitCount'], pixel_format['dwFlags']
                dwRGBABitMask = [pixel_format['dwRBitMask'], pixel_format['dwGBitMask'],
                    pixel_format['dwBBitMask'], pixel_format['dwABitMask']]
                if (dwRGBBitCount, dwRGBABitMask, pixelflags) == (16, [0x0F00, 0x00F0, 0x000F, 0xF000], 0x41):
                    block_size, base_format, pixel_bit_format = 2, 4, 1
                elif (dwRGBBitCount, dwRGBABitMask, pixelflags) == (16, [0x7C00, 0x03E0, 0x001F, 0x8000], 0x41):
                    block_size, base_format, pixel_bit_format = 2, 4, 2
                elif (dwRGBBitCount, dwRGBABitMask, pixelflags) == (16, [0xF800, 0x07E0, 0x001F, 0], 0x40):
                    block_size, base_format, pixel_bit_format = 2, 4, 3
                elif (dwRGBBitCount, dwRGBABitMask, pixelflags) == (32, [0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000], 0x41):
                    block_size, base_format, pixel_bit_format = 4, 5, 0
                elif pixelflags & 0x4 and header['pixel_format']['dwFourCC'] == 'DXT1':
                    block_size, base_format, pixel_bit_format = 8, 6, 6
                    use_alpha = 0 # BC1 has no alpha channels
                elif pixelflags & 0x4 and header['pixel_format']['dwFourCC'] == 'DXT3':
                    block_size, base_format, pixel_bit_format = 16, 7, 6
                elif pixelflags & 0x4 and header['pixel_format']['dwFourCC'] == 'DXT5':
                    block_size, base_format, pixel_bit_format = 16, 8, 6
                elif pixelflags & 0x4 and (header['pixel_format']['dwFourCC'] == 'DX10'
                    and header['dxt10_header']['dxgiFormat'] == 98):
                    block_size, base_format, pixel_bit_format = 16, 10, 6
                else:
                    return False # No support for anything but BC1, BC3, BC7 for now
                # IMIP 2nd value is MipMap type; 0 is none, 1 is type 1 and 2 is type 2 - I think we always use type 1.
                imip = b'IMIP' + struct.pack("<2I2HI", 12, 12, 1 if header['dwMipMapCount'] > 1 else 0, header['dwMipMapCount'] - 1, 0)
                ialp = b'IALP' + struct.pack("<2I2H", 8, 8, use_alpha, 0)
                idats = []
                for i in range(header['dwMipMapCount']):
                    mipWidth = max(1, header['dwWidth'] >> i)
                    mipHeight = max(1, header['dwHeight'] >> i)
                    if pixelflags & 0x4: # Block compression, e.g. BC7
                        expected_size = max(1,(mipWidth+3)//4) * max(1,(mipHeight+3)//4) * block_size
                    else:
                        expected_size = mipWidth * mipHeight * block_size
                    raw_tex_data = f.read(expected_size)
                    if pixel_tile_format == 4: # For now, support only PS4 tiled Morton swizzle
                        raw_tex_data = swizzle(raw_tex_data, mipHeight, mipWidth, block_size)
                    tex_data = create_data_blocks(raw_tex_data, compression_type)
                    idats.append(b'IDAT' + struct.pack("<2I2H", len(tex_data) + 8, 8, 0, i) + tex_data)
                idat = b''.join(idats)
                iend = b'IEND\x00\x00\x00\x00'
                data_size = 4 + 40 + len(imip) + len(ialp) + len(idat) + len(iend) #ITP\xff+IHDR+IMIP+IALP+IDAT+IEND - No support for IPAL/IHAS
                ihdr = b'IHDR' + struct.pack("<5I6HI", 32, 32, header['dwWidth'], header['dwHeight'], data_size,\
                    itp_revision, base_format, pixel_tile_format, pixel_bit_format, compression_type, multi_plane, 0)
                itp_block = b'ITP\xff' + ihdr + imip + ialp + idat + iend
        return(itp_block)
    else:
        return(False)

def create_texi (texture, tex_folder, use_alpha = 1, compression_type = 3, texi_type = 'TEXI'):
    if texture[-4:].lower() == '.dds':
        itp_block = create_itp ("{0}/{1}".format(tex_folder, texture), use_alpha, compression_type)
    else:
        itp_block = open("{0}/{1}".format(tex_folder, texture), 'rb').read()
    tex_name = texture.split('.itp')[0].split('.dds')[0]
    if not itp_block is False:
        if texi_type == 'TEXI':
            texi_block = (b'TEXI' + struct.pack("<I", len(itp_block)+36)
                + tex_name[:36].encode().ljust(36, b'\x00')
                + itp_block)
        else: # TEX2
            name_block = struct.pack("<I", len(tex_name) + 1) + tex_name.encode() + b'\x00'
            texi_block = (b'TEX2' + struct.pack("<I", len(itp_block)+len(name_block))
                + name_block + itp_block)
        return(texi_block)
    else:
        return(False)

# VPA7 is untested
def create_vpa78 (submeshes, bonemap, block_type = 'VPA8'):
    compression_type = 2
    vb_stream = io.BytesIO()
    ib_stream = io.BytesIO()
    vertices_metadata = bytearray()
    indices_metadata = bytearray()
    count = 0
    # Initialize bounding box
    bbox = {'min_x': float('inf'), 'min_y': float('inf'), 'min_z': float('inf'),
        'max_x': float('-inf'), 'max_y': float('-inf'), 'max_z': float('-inf')}
    infinite_box = True
    materials = []
    for i in range(len(submeshes)):
        stride_semantic = 'vb0 stride' if 'vb0 stride' in submeshes[i]['fmt'] else 'stride'
        if submeshes[i]['fmt'][stride_semantic] == '40' and submeshes[i]['vb'][0]['SemanticName'] == 'POSITION':
            #Enforce correct index size for VPAX and VP11
            submeshes[i]['fmt']['format'] = 'DXGI_FORMAT_R16_UINT'
            if not submeshes[i]['material']['material_name'] in [x['material_name'] for x in materials]:
                materials.append(submeshes[i]['material'])
            #Bounding box
            bbox_min = [min(x[0] for x in submeshes[i]['vb'][0]['Buffer']), min(x[1] for x in submeshes[i]['vb'][0]['Buffer']),\
                min(x[2] for x in submeshes[i]['vb'][0]['Buffer']), 1.0]
            bbox_max = [max(x[0] for x in submeshes[i]['vb'][0]['Buffer']), max(x[1] for x in submeshes[i]['vb'][0]['Buffer']),\
                max(x[2] for x in submeshes[i]['vb'][0]['Buffer']), 1.0]
            bbox_mid = [(bbox_min[0]+bbox_max[0])/2, (bbox_min[1]+bbox_max[1])/2, (bbox_min[2]+bbox_max[2])/2, 0.0]
            bbox['min_x'] = min(bbox['min_x'], bbox_min[0])
            bbox['min_y'] = min(bbox['min_y'], bbox_min[1])
            bbox['min_z'] = min(bbox['min_z'], bbox_min[2])
            bbox['max_x'] = max(bbox['max_x'], bbox_max[0])
            bbox['max_y'] = max(bbox['max_y'], bbox_max[1])
            bbox['max_z'] = max(bbox['max_z'], bbox_max[2])
            infinite_box = False
            #Construct local bone palette
            semantics = [x['SemanticName'] for x in submeshes[i]['vb']]
            if 'BLENDINDICES' in semantics:
                blendidx = semantics.index('BLENDINDICES')
                palette = sorted(list(set([0]) | set([x for y in [\
                    [submeshes[i]['vb'][blendidx]['Buffer'][j][k] for k in range(4)]\
                    for j in range(len(submeshes[i]['vb'][blendidx]['Buffer']))] for x in y])))
                if len(palette) > 9:
                    print("Warning!  Bone palette for submesh {} is greater than 9 groups, distortion may result!".format(i))
                    input("Press Enter to continue.")
                v_unk3 = [0, 4 if len(palette) == 4 else 5 if len(palette) > 4 else 3, 0, 0]
                bone_palette_dict = {palette[i]:i for i in range(len(palette))} # 0 should map to 0 (always unused)
                new_bone_index = [[bone_palette_dict[k] if k in bone_palette_dict else 0 for k in j] for j in submeshes[i]['vb'][blendidx]['Buffer']]
                submeshes[i]['vb'][blendidx]['Buffer'] = new_bone_index   
            if block_type == 'VPA8':
                if 'BLENDINDICES' in semantics:
                    bone_palette = [x * 3 for x in palette[1:10] + [0]*(10-len(palette))] # Exclude 0 (always unused)
                else:
                    bone_palette, v_unk3 = [0] * 9, [0,3,0,0]
                vpa8_subheader = [*bbox_mid,
                    0, # v_unk0
                    [x['material_name'] for x in materials].index(submeshes[i]['material']['material_name']),
                    0, # v_unk1
                    len(submeshes[i]['vb'][0]['Buffer']), # Number of vertices
                    *bbox_min,
                    *bbox_max,
                    *v_unk3,
                    *bone_palette]
                vertices_metadata.extend(struct.pack("<4f4I8f13I", *vpa8_subheader))
                indices_metadata.extend(struct.pack("<3I", 0, len([x for y in submeshes[i]['ib'] for x in y]), 0))
            else: #VPA7
                if 'BLENDINDICES' in semantics:
                    bone_palette = [x * 3 for x in palette[1:9] + [0]*(9-len(palette))] # Exclude 0 (always unused)
                else:
                    bone_palette, v_unk3 = [0] * 8, [0,3,0,0]
                vpa7_subheader = [len(submeshes[i]['vb'][0]['Buffer']), # Number of vertices - why twice?
                    *bbox_mid,
                    0, # v_unk0
                    [x['material_name'] for x in materials].index(submeshes[i]['material']['material_name']),
                    0, # v_unk1
                    len(submeshes[i]['vb'][0]['Buffer']), # Number of vertices
                    *bbox_min,
                    *bbox_max,
                    *v_unk3, # copied from VPA8 as I don't know what the correct values are for VPA7
                    *bone_palette]
                vertices_metadata.extend(struct.pack("<I4f4I8f12I", *vpa7_subheader))
                indices_metadata.extend(struct.pack("<I", len([x for y in submeshes[i]['ib'] for x in y])))
            write_vb_stream(submeshes[i]['vb'], vb_stream, submeshes[i]['fmt'], e = '<', interleave = True)
            write_ib_stream(submeshes[i]['ib'], ib_stream, submeshes[i]['fmt'], e = '<')
            count += 1
        else:
            print("Skipping submesh {}, wrong format.".format(i))
    bbox = bbox if infinite_box == False else {'min_x': 0.0, 'min_y': 0.0, 'min_z': 0.0,
        'max_x': 0.0, 'max_y': 0.0, 'max_z': 0.0}
    vb_stream.seek(0,0)
    vb_block = vb_stream.read()
    ib_stream.seek(0,0)
    ib_block = ib_stream.read()
    if block_type == 'VPA8':
        vb_data = b''.join([create_data_blocks(vb_block[i*0x40000:(i+1)*0x40000], compression_type)\
            for i in range((len(vb_block)-1)//0x40000+1)])
        ib_data = b''.join([create_data_blocks(ib_block[i*0x40000:(i+1)*0x40000], compression_type)\
            for i in range((len(ib_block)-1)//0x40000+1)])
        vb_meta = create_data_blocks (vertices_metadata, compression_type)
        ib_meta = create_data_blocks (indices_metadata, compression_type)
        vpa_stream = struct.pack("<3I", count, len(vb_block), len(ib_block) * 2) + vb_meta \
            + vb_data + ib_meta + ib_data
    else: # VPA7
        vb_data = create_data_blocks (vb_block, compression_type)
        ib_data = create_data_blocks (ib_block, compression_type)
        vpa_stream = struct.pack("<2I", count, len(vb_block)) + vertices_metadata + vb_data \
            + struct.pack("<I", len(ib_block) * 2) + indices_metadata + ib_data
    vb_stream.close()
    ib_stream.close()
    vpa_block = block_type.encode() + struct.pack("<I", len(vpa_stream)) + vpa_stream
    bbox_array = [[bbox['min_x'], bbox['min_y'], bbox['min_z'], 1.0], [bbox['max_x'] ,bbox['max_y'], bbox['max_z'], 1.0],\
        [(bbox['min_x'] + bbox['max_x'])/2, (bbox['min_y'] + bbox['max_y'])/2, (bbox['min_z'] + bbox['max_z'])/2,\
        numpy.linalg.norm(numpy.array([bbox['min_x'], bbox['min_y'], bbox['min_z']]) - numpy.array([bbox['max_x'], bbox['max_y'], bbox['max_z']]))/2.0]]
    bbox_block = b'BBOX' + struct.pack("<I", 48) + struct.pack("<12f", *[x for y in bbox_array for x in y])
    return(vpa_block, bbox_block, materials)

# Acceptable block types include 'VPA9', 'VPAX', 'VPAU', 'VP11'
def create_vpax (submeshes, block_type = 'VPAX'):
    attr_format = [1, 1, 1, 1, 2, 2, 3, 3, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1]
    attr_offset = [0, 16, 32, 48, 64, 68, 72, 76, 80, 96, 112, 128, 144, 148, 152, 156, 160, 172, 184, 192]
    attr_stride = [16, 16, 16, 16, 4, 4, 4, 4, 16, 16, 16, 16, 4, 4, 4, 4, 12, 12, 8, 8]
    attr_bitmask = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288]
    attr_len = {'VPA9': 16, 'VPAX': 16, 'VPAU': 20, 'VP11': 16}[block_type]
    # VPAU is uncompressed, and type is ignored
    if block_type == 'VPA9':
        compression_type = 2
    else:
        compression_type = 3
    indices_data = bytes()
    vertices_data = bytes()
    count = 0
    # Initialize bounding box
    bbox = {'min_x': float('inf'), 'min_y': float('inf'), 'min_z': float('inf'),
        'max_x': float('-inf'), 'max_y': float('-inf'), 'max_z': float('-inf')}
    infinite_box = True
    materials = []
    for i in range(len(submeshes)):
        expected_fmt = make_fmt(submeshes[i]['fmt_bitmask'], game_version = {'VPA9':1, 'VPAX':1, 'VP11':2, 'VPAU':1}[block_type])
        stride = int(expected_fmt['stride'])
        stride_semantic = 'vb0 stride' if 'vb0 stride' in submeshes[i]['fmt'] else 'stride'
        pos_semantic_num = [j for j in range(len(submeshes[i]['fmt']['elements']))
            if submeshes[i]['fmt']['elements'][j]['SemanticName'] == 'POSITION']
        pos_i = pos_semantic_num[0] if len(pos_semantic_num) > 0 else None
        if (submeshes[i]['fmt'][stride_semantic] == expected_fmt['stride']
                and submeshes[i]['vb'][0]['SemanticName'] == expected_fmt['elements'][0]['SemanticName']):
            #Enforce correct index size for VPAX and VP11
            submeshes[i]['fmt']['format'] = {'VPA9': 'DXGI_FORMAT_R16_UINT', 'VPAX': 'DXGI_FORMAT_R16_UINT',
                'VPAU': 'DXGI_FORMAT_R16_UINT', 'VP11': 'DXGI_FORMAT_R32_UINT'}[block_type]
            if not submeshes[i]['material']['material_name'] in [x['material_name'] for x in materials]:
                materials.append(submeshes[i]['material'])
            if pos_i is not None:
                bbox_min = [min(x[0] for x in submeshes[i]['vb'][pos_i]['Buffer']), min(x[1] for x in submeshes[i]['vb'][pos_i]['Buffer']),\
                    min(x[2] for x in submeshes[i]['vb'][pos_i]['Buffer']), 0.0]
                bbox_max = [max(x[0] for x in submeshes[i]['vb'][pos_i]['Buffer']), max(x[1] for x in submeshes[i]['vb'][pos_i]['Buffer']),\
                    max(x[2] for x in submeshes[i]['vb'][pos_i]['Buffer']), 0.0]
                bbox_mid = [(bbox_min[0]+bbox_max[0])/2, (bbox_min[1]+bbox_max[1])/2, (bbox_min[2]+bbox_max[2])/2, 0.0]
                bbox['min_x'] = min(bbox['min_x'], bbox_min[0])
                bbox['min_y'] = min(bbox['min_y'], bbox_min[1])
                bbox['min_z'] = min(bbox['min_z'], bbox_min[2])
                bbox['max_x'] = max(bbox['max_x'], bbox_max[0])
                bbox['max_y'] = max(bbox['max_y'], bbox_max[1])
                bbox['max_z'] = max(bbox['max_z'], bbox_max[2])
                infinite_box = False
            else:
                bbox_min = [0.0, 0.0, 0.0, 0.0]
                bbox_max = [0.0, 0.0, 0.0, 0.0]
                bbox_mid = [0.0, 0.0, 0.0, 0.0]
            vpac_header = b'VPAC\x00\x00\x01\x00' + struct.pack("<4f", *bbox_mid) + struct.pack("<4f", *bbox_min) + struct.pack("<4f", *bbox_max) \
                + struct.pack("<4I", len(submeshes[i]['vb'][0]['Buffer']), len(submeshes[i]['vb'][0]['Buffer'])*stride, submeshes[i]['fmt_bitmask'], attr_len) \
                + struct.pack("<{}I".format(attr_len), *attr_format[:attr_len]) \
                + struct.pack("<{}I".format(attr_len), *attr_offset[:attr_len]) \
                + struct.pack("<{}I".format(attr_len), *attr_stride[:attr_len]) \
                + struct.pack("<{}I".format(attr_len), *attr_bitmask[:attr_len]) \
                + struct.pack("<9I", [x['material_name'] for x in materials].index(submeshes[i]['material']['material_name']), 0, 0, 0, 0, 0, 0, 0, 0)
            with io.BytesIO() as vb_stream:
                vb_stream.write(vpac_header)
                if stride_semantic == 'vb0 stride':
                    write_seg_vb_stream(submeshes[i]['vb'], vb_stream, submeshes[i]['fmt'], '0', e = '<', interleave = True)
                else:
                    write_vb_stream(submeshes[i]['vb'], vb_stream, submeshes[i]['fmt'], e = '<', interleave = True)
                if not block_type == 'VPAU':
                    while vb_stream.tell() % 64 > 0:
                        vb_stream.write(b'\x00')
                vb_stream.seek(0,0)
                if block_type == 'VPAU':
                    vb_data = vb_stream.read()
                elif block_type == 'VPA9':
                    vb_block = vb_stream.read()
                    vb_data = b''.join([create_data_blocks(vb_block[i*0x40000:(i+1)*0x40000], compression_type)\
                        for i in range((len(vb_block)-1)//0x40000+1)])
                else:
                    vb_data = create_data_blocks (vb_stream.read(), compression_type)
                vertices_data += struct.pack("<I", vb_stream.tell()) + vb_data
            with io.BytesIO() as ib_stream:
                write_ib_stream(submeshes[i]['ib'], ib_stream, submeshes[i]['fmt'], e = '<')
                ib_stream.seek(0,0)
                if block_type == 'VPAU':
                    ib_data = ib_stream.read()
                elif block_type == 'VPA9':
                    ib_block = ib_stream.read()
                    ib_data = b''.join([create_data_blocks(ib_block[i*0x40000:(i+1)*0x40000], compression_type)\
                        for i in range((len(ib_block)-1)//0x40000+1)])
                else:
                    ib_data = create_data_blocks (ib_stream.read(), compression_type)
                indices_data += struct.pack("<I", ib_stream.tell()//{'VPA9': 2, 'VPAX': 2, 'VPAU': 2, 'VP11': 4}[block_type]) + ib_data
            count += 1
        else:
            print("Skipping submesh {}, wrong format.".format(i))
    vpax_stream = struct.pack("<I", count) + vertices_data + indices_data
    vpax_block = block_type.encode() + struct.pack("<I", len(vpax_stream)) + vpax_stream
    bbox = bbox if infinite_box == False else {'min_x': 0.0, 'min_y': 0.0, 'min_z': 0.0,
        'max_x': 0.0, 'max_y': 0.0, 'max_z': 0.0}
    bbox_array = [[bbox['min_x'], bbox['min_y'], bbox['min_z'], 1.0], [bbox['max_x'] ,bbox['max_y'], bbox['max_z'], 1.0],\
        [(bbox['min_x'] + bbox['max_x'])/2, (bbox['min_y'] + bbox['max_y'])/2, (bbox['min_z'] + bbox['max_z'])/2,\
        numpy.linalg.norm(numpy.array([bbox['min_x'], bbox['min_y'], bbox['min_z']]) - numpy.array([bbox['max_x'], bbox['max_y'], bbox['max_z']]))/2.0]]
    bbox_block = b'BBOX' + struct.pack("<I", 48) + struct.pack("<12f", *[x for y in bbox_array for x in y])
    return(vpax_block, bbox_block, materials)

def create_mat4 (materials, compression_type = 2):
    def encode_mat4_string (string):
        return (string.encode().ljust(0x40, b'\x00'))
    uncompressed_data = bytearray()
    for i in range(len(materials)):
        uncompressed_data.extend(encode_mat4_string(materials[i]['material_name']))
        for j in range(4):
            uncompressed_data.extend(encode_mat4_string(materials[i]['textures'][j]['name']))
        uncompressed_data.extend(struct.pack("<12f", *materials[i]['float_list']))
        uncompressed_data.extend(struct.pack("<fifi", *materials[i]['unk_values']))
    compressed_data = struct.pack("<I", len(materials)) + create_data_blocks (uncompressed_data, compression_type)
    mat4_block = b'MAT4' + struct.pack("<I", len(compressed_data)) + compressed_data
    return(mat4_block)

def create_mat6 (materials, compression_type = 3):
    compressed_data = struct.pack("<I", len(materials))
    for i in range(len(materials)):
        part1 = struct.pack("<7I", *materials[i]['unk0']) \
            + struct.pack("<3I", len(materials[i]['parameters']), len(materials[i]['textures'])*16, len(materials[i]['textures'])) \
            + b''.join([struct.pack("<4f", *x) for x in materials[i]['parameters']]) \
            + b''.join([struct.pack("<4I", *x['flags']) for x in materials[i]['textures']])
        part1 += b''.join([b'\x00' for _ in range((-(len(part1) + 12)) % 64)])
        part2 = struct.pack("<I", 64) + materials[i]['material_name'].encode().ljust(64, b'\x00') \
            + struct.pack("<I", 32) + b''.join([x['name'].encode().ljust(32, b'\x00') for x in materials[i]['textures']])
        part2 += b''.join([b'\x00' for _ in range((-(len(part2) + 12)) % 64)])
        block = b'MATM' + struct.pack("<2I", materials[i]['MATM_flags'], len(part1)+12) + part1 \
            + b'MATE' + struct.pack("<2I", materials[i]['MATE_flags'], len(part2)+12) + part2
        compressed_data += struct.pack("<I", len(block)) + create_data_blocks(block, compression_type) 
    mat6_block = b'MAT6' + struct.pack("<I", len(compressed_data)) + compressed_data
    return(mat6_block)

def create_matu (materials):
    matu_data = struct.pack("<I", len(materials))
    for i in range(len(materials)):
        part1 = struct.pack("<7I", *materials[i]['unk0']) \
            + struct.pack("<3I", len(materials[i]['parameters']), len(materials[i]['textures'])*16, len(materials[i]['textures'])) \
            + b''.join([struct.pack("<4f", *x) for x in materials[i]['parameters']]) \
            + b''.join([struct.pack("<4I", *x['flags']) for x in materials[i]['textures']])
        part1 += b''.join([b'\x00' for _ in range((-(len(part1) + 12)) % 64)])
        part2 = struct.pack("<I", 64) + materials[i]['material_name'].encode().ljust(64, b'\x00') \
            + struct.pack("<I", 0x100) + b''.join([x['name'].encode().ljust(0x100, b'\x00') for x in materials[i]['textures']])
        part2 += b'\x00' * 0x2C
        block = b'MATM' + struct.pack("<2I", materials[i]['MATM_flags'], len(part1)+12) + part1 \
            + b'MATE' + struct.pack("<2I", materials[i]['MATE_flags'], len(part2)+12) + part2
        matu_data += struct.pack("<I", len(block)) + block
    matu_block = b'MATU' + struct.pack("<I", len(matu_data)) + matu_data
    return(matu_block)

# .bonemap files are in the exact same format as .vgmap files.
def create_bon3 (bonemap, node_name, compression_type = 3):
    true_map = [k for k, v in sorted(bonemap.items(), key=lambda kv: kv[1])][1:] #Ignore the first entry, as the map starts at 1
    bon3_block_data = (struct.pack("<I", 256) + node_name.encode().ljust(64, b'\x00')
        + struct.pack("<I", len(true_map))
        + create_data_blocks(b''.join([x.encode().ljust(64, b'\x00') for x in true_map]), compression_type)
        + create_data_blocks(b''.join([x.encode().ljust(64, b'\x00') for x in true_map]), compression_type)
        + create_data_blocks(b''.join([struct.pack("<16f", 1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1) for _ in true_map]), compression_type))
    return(b'BON3' + struct.pack("<I", len(bon3_block_data)) + bon3_block_data)

def create_rty2 (rty2_data):
    rty2_block_data = struct.pack("<I", rty2_data['material_variant']) \
        + struct.pack("<B", rty2_data['unknown']) \
        + struct.pack("<3f", *rty2_data['v0'])
    return(b'RTY2' + struct.pack("<I", len(rty2_block_data)) + rty2_block_data)

def create_rty3 (rty3_data):
    rty3_block_data = struct.pack("<B", rty3_data['material_variant']) \
        + struct.pack("<B", rty3_data['unknown'])
    return(b'RTY3' + struct.pack("<I", len(rty3_block_data)) + rty3_block_data)

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
            contents[section_info["data"]["name"]] = {'offset': section_info["section_start_offset"]-8, 'contents': [], 'offsets': []}
        else:
            contents[info_section]['contents'].append(section_info["type"])
            contents[info_section]['offsets'].append(section_info["section_start_offset"])
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
        elif magic == 'RTY3':
            rty_data = parse_rty3_block(f)
            return rty_data["material_variant"]
        else:
            f.seek(size,1)
    return -1

def return_vpau_bitmask(f, it3_section):
    f.seek(it3_section['offset'])
    while f.tell() < it3_section['offset'] + it3_section['length']:
        magic = f.read(4).decode("ASCII")
        size, = struct.unpack("<I", f.read(4))
        if magic == 'VPAU':
            f.seek(0x48,1)
            fmt_bitmask, = struct.unpack("<I", f.read(4))
            return(fmt_bitmask)
        else:
            f.seek(size,1)
    return -1

def process_it3 (it3_filename, import_noskel = False, use_gl_order = False):
    if not os.path.isdir(it3_filename[:-4]):
        print("{} is missing a model folder, skipping.".format(it3_filename))
        return
    with open(it3_filename,"rb") as f:
        it3_contents = rapid_parse_it3 (f)
        # Will read data from JSON file, or load original data from the mdl file if JSON is missing
        try:
            material_struct = read_struct_from_json(it3_filename[:-4] + '/materials_metadata.json')
        except (FileNotFoundError, json.JSONDecodeError):
            material_struct = {}
            print("{0}/materials_metadata.json missing or unreadable, reading data from {0}.it3 instead...".format(it3_filename[:-4]))
            to_process_mat = [x for x in it3_contents if 'MAT4' in it3_contents[x]['contents']\
                or 'MAT6' in it3_contents[x]['contents'] or 'MATU' in it3_contents[x]['contents']]
            for section in to_process_mat:
                mat4 = []
                mat6 = []
                rty2 = {}
                f.seek(it3_contents[section]['offset'])
                use_rty = None
                while f.tell() < it3_contents[section]['offset']+it3_contents[section]['length']:
                    section_info = {}
                    section_info["type"] = f.read(4).decode('ASCII')
                    section_info["size"], = struct.unpack("<I",f.read(4))
                    if (section_info["type"] == 'MAT4'):
                        mat4 = parse_mat4_block(f)
                    elif (section_info["type"] == 'MAT6'):
                        mat6 = parse_mat6_block(f)
                    elif (section_info["type"] == 'RTY2'):
                        rty2 = parse_rty2_block(f)
                        use_rty = 'rty2'
                    elif (section_info["type"] == 'MATU'):
                        mat6 = parse_matu_block(f)
                    elif (section_info["type"] == 'RTY3'):
                        rty3 = parse_rty3_block(f)
                        use_rty = 'rty3'
                    else:
                        f.seek(section_info["size"],1)
                mats = {}
                for i in range(len(mat4)):
                    material_name = mat4[i].pop('material_name')
                    mats[material_name] = mat4[i]
                for i in range(len(mat6)):
                    material_name = mat6[i].pop('material_name')
                    mats[material_name] = mat6[i]
                material_struct[section] = {}
                if not use_rty is None:
                    material_struct[section]['{}_shader_assignment'.format(use_rty)] = rty2 if use_rty == 'rty2' else rty3
                material_struct[section]['material_parameters'] = mats
        to_process_tex = [x for x in it3_contents if 'TEXI' in it3_contents[x]['contents']
            or 'TEX2' in it3_contents[x]['contents']] #TEXF someday?
        to_process_vp = [x for x in it3_contents if any(y in it3_contents[x]['contents'] for y in ['VPA7','VPA8','VPA9','VPAX','VPAU','VP11'])]
        if import_noskel == False:
            to_process_vp = [x for x in to_process_vp if return_rty2_material(f, it3_contents[x]) != 8]
        new_it3_chunks = []
        # All native IT3 files use the same compression type throughout, and VPA types are never mixed in native files
        compression_type = 2 # Set a default; I don't think there are any IT3s without VPA sections but just in case
        texi_texture_names = []
        texi_type = 'TEXI' # Ys 8 and previous use TEXI, Ys 9 uses TEX2 - if a TEX2 is detected, use TEX2 exclusively
        for section in it3_contents:
            # VPA blocks in TEX sections will not be altered - may change if needed in future
            if section in to_process_vp:
                rty_type = 'RTY2'
                if 'VP11' in it3_contents[section]['contents']:
                    block_type = 'VP11'
                    mat_type = 'MAT6'
                    compression_type = 3
                    default_fmt_bitmask = 0xFFFF
                elif 'VPAU' in it3_contents[section]['contents']:
                    block_type = 'VPAU'
                    mat_type = 'MATU'
                    rty_type = 'RTY3'
                    compression_type = 3
                    default_fmt_bitmask = return_vpau_bitmask(f, it3_contents[section])
                elif 'VPAX' in it3_contents[section]['contents']:
                    block_type = 'VPAX'
                    mat_type = 'MAT6'
                    compression_type = 3
                    default_fmt_bitmask = 0xFFFF
                elif 'VPA9' in it3_contents[section]['contents']:
                    block_type = 'VPA9'
                    mat_type = 'MAT6'
                    compression_type = 2
                    default_fmt_bitmask = 0xFFFF
                elif 'VPA8' in it3_contents[section]['contents']:
                    block_type = 'VPA8'
                    mat_type = 'MAT4'
                    compression_type = 2
                    default_fmt_bitmask = 0 # Unused
                else:
                    block_type = 'VPA7'
                    mat_type = 'MAT4'
                    compression_type = 2
                    default_fmt_bitmask = 0 # Unused
                # Build VPAX/VP11, BBOX, MAT6
                rty_shader_assignment = "{}_shader_assignment".format(rty_type).lower()
                safe_sectionname = "".join([x if x not in "\\/:*?<>|" else "_" for x in section])
                search_pattern = os.path.join(it3_filename[:-4], "meshes", f"{glob.escape(safe_sectionname)}_*.fmt")
                valid_pattern = re.compile(rf"^{re.escape(safe_sectionname)}_\d+$")
                submeshfiles = sorted([filepath[:-4] for filepath in glob.glob(search_pattern)
                    if valid_pattern.match(os.path.basename(filepath)[:-4])])
                fmt_bitmask_file = it3_filename[:-4] + '/meshes/{}.fmt_bitmask'.format(safe_sectionname)
                submeshes = []
                # Read in custom bonemap if it exists
                if os.path.exists(it3_filename[:-4] + '/meshes/{}.bonemap'.format(safe_sectionname)):
                    bonemap = read_struct_from_json(it3_filename[:-4] + '/meshes/{}.bonemap'.format(safe_sectionname))
                    bon3_block = create_bon3(bonemap, section, compression_type)
                    custom_bonemap = True
                else:
                    bonemap = {section: 0}
                    if 'BON3' in it3_contents[section]['contents']:
                        f.seek(it3_contents[section]['offsets'][it3_contents[section]['contents'].index('BON3')])
                        bon3_data = parse_bon3_block (f)
                        bonemap.update({bon3_data['joints'][i]:i+1 for i in range(len(bon3_data['joints']))})
                    custom_bonemap = False
                for j in range(len(submeshfiles)):
                    print("Reading submesh {0}...".format(submeshfiles[j]))
                    try:
                        fmt = read_fmt(submeshfiles[j] + '.fmt')
                        ib = read_ib(submeshfiles[j] + '.ib', fmt)
                        if not use_gl_order:
                            ib = [[x[0],x[2],x[1]] for x in ib] # Swap DirectX triangles back to OpenGL
                        vb = read_vb(submeshfiles[j] + '.vb', fmt)
                        try:
                            vgmap = read_struct_from_json(submeshfiles[j] + '.vgmap')
                            vgmap_keys, bonemap_keys = list(vgmap.keys()), list(bonemap.keys())
                            # The bone corresponding to zero needs to be renamed to the internal bonemap 0 name
                            vgmap = {(bonemap_keys[0] if v == 0 else k): v for k, v in vgmap.items()}
                            if not (all([True if x in bonemap else False for x in vgmap])\
                                and all([bonemap[x] == vgmap[x] for x in vgmap])):
                                print("Warning! {}.vgmap does not match the internal skin node tree!".format(submeshfiles[j]))
                                rev_vgmap = {vgmap[k]:k for k in vgmap}
                                semantics = [x['SemanticName'] for x in vb]
                                if 'BLENDINDICES' in semantics and ('BLENDWEIGHT' in semantics or 'BLENDWEIGHTS' in semantics):
                                    vg_index = semantics.index('BLENDINDICES')
                                    if 'BLENDWEIGHT' in semantics:
                                        wt_index = semantics.index('BLENDWEIGHT')
                                    else:
                                        wt_index = semantics.index('BLENDWEIGHTS')
                                    indices = [x for y in vb[vg_index]['Buffer'] for x in y]
                                    weights = [x for y in vb[wt_index]['Buffer'] for x in y]
                                    true_indices = sorted(list(set([indices[k] for k in range(len(indices)) if weights[k] > 0.0])))
                                    used_vg = [rev_vgmap.get(z,0) for z in true_indices]
                                    if all([x in bonemap.keys() for x in used_vg]):
                                        print("VGMap appears compatible, attempting automatic remap...")
                                        new_buffer = []
                                        for k in range(len(vb[vg_index]['Buffer'])):
                                            new_buffer.append([bonemap[y] if y in bonemap else 0 for y \
                                                in [rev_vgmap.get(z,0) for z in vb[vg_index]['Buffer'][k]]])
                                        vb[vg_index]['Buffer'] = new_buffer
                                    else:
                                        print("VGMap incompatible with this mesh, automatic remap not possible.")
                                        print("This model will likely have major animation distortions and may crash the game.")
                                        input("Press Enter to continue.")
                                else:
                                    pass # No weights, sanity check unnecessary
                        except FileNotFoundError:
                            if len(bonemap) > 1:
                                print("{}.vgmap not found, vertex group sanity check skipped.".format(submeshfiles[j]))
                        if os.path.exists(fmt_bitmask_file):
                            fmt_bitmask = json.loads(open(fmt_bitmask_file,'rb').read())['fmt_bitmask']
                        else:
                            fmt_bitmask = default_fmt_bitmask
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
                        submeshes.append({'fmt': fmt, 'ib': ib, 'vb': vb, 'material': material, 'fmt_bitmask': fmt_bitmask})
                    except FileNotFoundError:
                        print("Submesh {0} not found, skipping...".format(submeshfiles[j]))
                        continue
                if len(submeshes) == 0:
                    # Insert an empty mesh
                    if block_type in ['VPA9', 'VPAX', 'VPAU', 'VP11']:
                        fmt = make_fmt(default_fmt_bitmask, {'VPA9':1, 'VPAX':1, 'VPAU': 1, 'VP11':2}[block_type])
                        submeshes.append({'fmt': fmt, 'ib': [],\
                        'vb': read_vb_stream(b''.join([b'\x00' for _ in range(int(fmt['stride'])*3)]), fmt),\
                        'material': {"material_name": "", "MATM_flags": 65793, "MATE_flags": 65793,\
                            "unk0": [28,0,0,0,0,0,0], "parameters": [], "textures": []}})
                    else: # VPA7 / VPA8
                        fmt = make_vpa8_fmt()
                        submeshes.append({'fmt': fmt, 'ib': [[0,0,0]],\
                        'vb': read_vb_stream(b''.join([b'\x00' for _ in range(40)]), fmt),\
                        'material': {"material_name": "",\
                            "textures": [{"name": ""},{"name": ""},{"name": ""},{"name": ""}],\
                            "float_list": [1.0,1.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],\
                            "unk_values": [0.0,0,1.0,0]}})
                if block_type in ['VPA9', 'VPAX', 'VPAU', 'VP11']:
                    vp_block, bbox_block, materials = create_vpax(submeshes, block_type = block_type)
                else: # VPA7 / VPA8
                    vp_block, bbox_block, materials = create_vpa78(submeshes, bonemap, block_type = block_type)
                if mat_type == 'MAT6':
                    mat6_block = create_mat6(materials, compression_type)
                elif mat_type == 'MATU':
                    matu_block = create_matu(materials)
                else: # MAT4
                    mat4_block = create_mat4(materials, compression_type)
                custom_rty = False
                if rty_shader_assignment in material_struct.get(section, {}):
                    if rty_type == 'RTY3':
                        rty_block = create_rty3(material_struct[section][rty_shader_assignment])
                    else:
                        rty_block = create_rty2(material_struct[section][rty_shader_assignment])
                    custom_rty = True
                f.seek(it3_contents[section]['offset'])
                while f.tell() < it3_contents[section]['offset']+it3_contents[section]['length']:
                    section_info = {}
                    section_info["type"] = f.read(4).decode('ASCII')
                    section_info["size"], = struct.unpack("<I",f.read(4))
                    current_offset = f.tell()
                    if (section_info["type"] in ['VPA7', 'VPA8', 'VPA9', 'VPAX', 'VPAU', 'VP11']):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3_chunks.append(vp_block)
                    elif (section_info["type"] == 'BBOX'):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3_chunks.append(bbox_block)
                    elif (section_info["type"] == 'MAT6'):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3_chunks.append(mat6_block)
                    elif (section_info["type"] == 'MATU'):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3_chunks.append(matu_block)
                    elif (section_info["type"] == 'MAT4'):
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3_chunks.append(mat4_block)
                    elif (section_info["type"] == 'BON3') and custom_bonemap == True:
                        f.seek(section_info["size"],1)
                        if len(submeshes) > 0:
                            new_it3_chunks.append(bon3_block)
                    elif (section_info["type"] == rty_type) and custom_rty == True:
                        f.seek(section_info["size"],1)
                        new_it3_chunks.append(rty_block)
                    elif (section_info["type"] == 'TEXI'):
                        texi_texture_names.append(f.read(36).split(b'\x00')[0].decode('ASCII'))
                        f.seek(current_offset + section_info["size"])
                    elif (section_info["type"] == 'TEX2'):
                        length, = struct.unpack("<I", f.read(4))
                        texi_texture_names.append(f.read(length).split(b'\x00')[0].decode('ASCII'))
                        texi_type = 'TEX2'
                        f.seek(current_offset + section_info["size"])
                    else:
                        new_it3_chunks.append(section_info["type"].encode() + struct.pack("<I", section_info["size"])
                            + f.read(section_info["size"]))
            elif section in to_process_tex: 
                f.seek(it3_contents[section]['offset'])
                while f.tell() < it3_contents[section]['offset']+it3_contents[section]['length']:
                    section_info = {}
                    section_info["type"] = f.read(4).decode('ASCII')
                    section_info["size"], = struct.unpack("<I",f.read(4))
                    current_offset = f.tell()
                    if (section_info["type"] == 'TEXI'):
                        texi_texture_names.append(f.read(36).split(b'\x00')[0].decode('ASCII'))
                        f.seek(current_offset + section_info["size"])
                    elif (section_info["type"] == 'TEX2'):
                        length, = struct.unpack("<I", f.read(4))
                        texi_texture_names.append(f.read(length).split(b'\x00')[0].decode('ASCII'))
                        texi_type = 'TEX2'
                        f.seek(current_offset + section_info["size"])
                    else:
                        new_it3_chunks.append(section_info["type"].encode() + struct.pack("<I", section_info["size"])
                            + f.read(section_info["size"]))
            else:
                f.seek(it3_contents[section]['offset'])
                new_it3_chunks.append(f.read(it3_contents[section]['length']))
        # Append all textures to the end of the IT3 file
        textures_imported = []
        if os.path.exists(it3_filename[:-4] + '/textures'):
            textures = [os.path.basename(x) for x in glob.glob(it3_filename[:-4] + '/textures/*.itp')]
            textures.extend([os.path.basename(x) for x in glob.glob(it3_filename[:-4] + '/textures/*.dds')\
                if not os.path.basename(x).replace('.dds','.itp') in textures])
            alpha_data = {}
            if os.path.exists(it3_filename[:-4] + '/textures/__alpha_data.json'):
                with open(it3_filename[:-4] + '/textures/__alpha_data.json','rb') as f2:
                    alpha_data = json.loads(f2.read())
            for texture in textures:
                use_alpha = alpha_data[texture[:-4]] if texture[:-4] in alpha_data else 0
                new_itp = create_texi (texture, it3_filename[:-4] + '/textures', use_alpha, compression_type, texi_type)
                if new_itp != False:
                    print("Importing {0}.".format(texture))
                    new_it3_chunks.append(new_itp)
                    textures_imported.append(texture[:-4])
                else:
                    print("Unable to import {}.".format(texture))
        new_it3 = b''.join(new_it3_chunks)
        # Report any deleted textures
        deleted_textures = [x for x in texi_texture_names if x not in textures_imported]
        if len(deleted_textures) > 0:
            print("Warning: These textures were not found and have been removed from the IT3: {}".format(deleted_textures))
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
    multiprocessing.freeze_support()
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
        parser.add_argument('-g', '--use_gl_order', help="Use OpenGL index buffer format", action="store_true")
        parser.add_argument('it3_filename', help="Name of it3 file to import into (required).")
        args = parser.parse_args()
        if os.path.exists(args.it3_filename) and args.it3_filename[-4:].lower() == '.it3':
            process_it3(args.it3_filename, import_noskel = args.import_noskel, use_gl_order = args.use_gl_order)
    else:
        it3_files = glob.glob('*.it3')
        it3_files = [x for x in it3_files if os.path.isdir(x[:-4])]
        for i in range(len(it3_files)):
            process_it3(it3_files[i])