# Tool to manipulate Ys VIII models in it3 format.  Dumps meshes for
# import into Blender.  Based on TwnKey's dumper (github/TwnKey/YsVIII_model_dump).
# Usage:  Run by itself without commandline arguments and it will read only the mesh section of
# every model it finds in the folder and output fmt / ib / vb files.
#
# For command line options, run:
# /path/to/python3 ys8_it3_export_meshes.py --help
#
# Requires lib_fmtibvb.py, put in the same directory
#
# GitHub eArmada8/Ys8_IT3

import struct, math, base64, io, json, os, sys, glob
from itertools import chain
from lib_fmtibvb import *

# This script outputs non-empty vgmaps by default, change the following line to True to change
complete_vgmaps_default = False

def make_fmt(mask, game_version = 1):
    fmt = {'stride': '0', 'topology': 'trianglelist', 'format':\
        "DXGI_FORMAT_R{0}_UINT".format([16,32][game_version-1]), 'elements': []}
    element_id, stride = 0, 0
    semantic_index = {'COLOR': 0, 'TEXCOORD': 0, 'UNKNOWN': 0} # Counters for multiple indicies
    elements = []
    for i in range(16):
        if mask & 1 << i:
            # I think order matters in this dict, so we will define the entire structure with default values
            element = {'id': '{0}'.format(element_id), 'SemanticName': '', 'SemanticIndex': '0',\
                'Format': '', 'InputSlot': '0', 'AlignedByteOffset': '',\
                'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}
            if i == 0:
                element['SemanticName'] = 'POSITION'
                element['Format'] = 'R32G32B32A32_FLOAT'
            elif i == 4:
                element['SemanticName'] = 'NORMAL'
                element['Format'] = 'R8G8B8A8_SNORM'
            elif i in [6,7]:
                element['SemanticName'] = 'COLOR'
                element['SemanticIndex'] = str(semantic_index['COLOR'])
                element['Format'] = 'R8G8B8A8_UNORM'
                semantic_index['COLOR'] += 1
            elif i in [8,9]:
                element['SemanticName'] = 'TEXCOORD'
                element['SemanticIndex'] = str(semantic_index['TEXCOORD'])
                element['Format'] = 'R32G32B32A32_FLOAT' #Actually R32G32 but Blender can ignore the padding
                semantic_index['TEXCOORD'] += 1
            elif i == 12:
                element['SemanticName'] = 'BLENDWEIGHTS'
                element['Format'] = 'R8G8B8A8_UNORM'
            elif i == 14:
                element['SemanticName'] = 'BLENDINDICES'
                element['Format'] = 'R8G8B8A8_UINT'
            else:
                element['SemanticName'] = 'UNKNOWN'
                element['SemanticIndex'] = str(semantic_index['UNKNOWN'])
                if i & 0xF0F0:
                    element['Format'] = 'R8G8B8A8_UINT'
                else:
                    element['Format'] = 'R32G32B32A32_UINT'
                semantic_index['UNKNOWN'] += 1
            element['AlignedByteOffset'] = str(stride)
            stride += {True: 16, False: 4}[not (1<<i & 0xF0F0)] # 0-3 and 8-11 are stride 16, 4-7 and 12-15 are stride 4
            element_id += 1
            elements.append(element)
    fmt['stride'] = str(stride)
    fmt['elements'] = elements
    return(fmt)

def make_88_fmt():
    return({'stride': '88', 'topology': 'trianglelist', 'format': 'DXGI_FORMAT_R32_UINT',\
        'elements': [{'id': '0', 'SemanticName': 'POSITION', 'SemanticIndex': '0',\
        'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '0',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '1',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '0',\
        'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '16',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '2',\
        'SemanticName': 'NORMAL', 'SemanticIndex': '0', 'Format': 'R8G8B8A8_SNORM',\
        'InputSlot': '0', 'AlignedByteOffset': '32', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '3',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '1', 'Format': 'R8G8B8A8_SNORM',\
        'InputSlot': '0', 'AlignedByteOffset': '36', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '4', 'SemanticName': 'COLOR', 'SemanticIndex': '0',\
        'Format': 'R8G8B8A8_UNORM', 'InputSlot': '0', 'AlignedByteOffset': '40',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '5',\
        'SemanticName': 'COLOR', 'SemanticIndex': '1', 'Format': 'R8G8B8A8_UNORM',\
        'InputSlot': '0', 'AlignedByteOffset': '44', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '6', 'SemanticName': 'TEXCOORD',\
        'SemanticIndex': '0', 'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0',\
        'AlignedByteOffset': '48', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '7', 'SemanticName': 'TEXCOORD',\
        'SemanticIndex': '1', 'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0',\
        'AlignedByteOffset': '64', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '8', 'SemanticName': 'BLENDWEIGHTS',\
        'SemanticIndex': '0', 'Format': 'R8G8B8A8_UNORM', 'InputSlot': '0',\
        'AlignedByteOffset': '80', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '9', 'SemanticName': 'BLENDINDICES',\
        'SemanticIndex': '0', 'Format': 'R8G8B8A8_UINT', 'InputSlot': '0',\
        'AlignedByteOffset': '84', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}]})

def make_vpa8_fmt():
    return({'stride': '40', 'topology': 'trianglelist', 'format': 'DXGI_FORMAT_R16_UINT',\
    'elements': [{'id': '0', 'SemanticName': 'POSITION', 'SemanticIndex': '0',\
    'Format': 'R32G32B32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '0',\
    'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '1',\
    'SemanticName': 'TEXCOORD', 'SemanticIndex': '0', 'Format': 'R32G32_FLOAT',\
    'InputSlot': '0', 'AlignedByteOffset': '12', 'InputSlotClass': 'per-vertex',\
    'InstanceDataStepRate': '0'}, {'id': '2', 'SemanticName': 'COLOR',\
    'SemanticIndex': '0', 'Format': 'R8G8B8A8_UNORM', 'InputSlot': '0',\
    'AlignedByteOffset': '20', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'},\
    {'id': '3', 'SemanticName': 'COLOR', 'SemanticIndex': '1', 'Format': 'R8G8B8A8_UNORM',\
    'InputSlot': '0', 'AlignedByteOffset': '24', 'InputSlotClass': 'per-vertex',\
    'InstanceDataStepRate': '0'}, {'id': '5', 'SemanticName': 'BLENDINDICES',\
    'SemanticIndex': '0', 'Format': 'R8G8B8A8_UINT', 'InputSlot': '0',\
    'AlignedByteOffset': '28', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'},\
    {'id': '4', 'SemanticName': 'BLENDWEIGHTS', 'SemanticIndex': '0',\
    'Format': 'R8G8B8A8_SNORM', 'InputSlot': '0', 'AlignedByteOffset': '32',\
    'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '6',\
    'SemanticName': 'NORMAL', 'SemanticIndex': '0', 'Format': 'R8G8B8A8_SNORM',\
    'InputSlot': '0', 'AlignedByteOffset': '36', 'InputSlotClass': 'per-vertex',\
    'InstanceDataStepRate': '0'}]})

def parse_data_block_new (f, block_size, is_compressed):
    # TODO: Find out what compression algorithm this is, and implement it using the standard library
    contents = bytes()
    if is_compressed:
        start = f.tell()
        while f.tell() < start + block_size - 4:
            current_byte1, current_byte2 = struct.unpack("<2B", f.read(2))
            if (current_byte1 == 0):
                contents += f.read(current_byte2)
            else:
                contents += b''.join([contents[-(current_byte2+1):]\
                    for x in range((current_byte1 // (current_byte2+1)) + 1)])[0:current_byte1]
                contents += f.read(1)
    else:
        contents = f.read(block_size - 4)
    return(contents)

# Thank you to uyjulian, source: https://gist.github.com/uyjulian/a6ba33dc29858327ffa0db57f447abe5
# Reference: CEgPacks2::UnpackBZMode2
# Also known as falcom_compress / BZ / BZip / zero method
def decompress(buffer, output, size):
    offset = 0 # u16
    bits = 8 # 8 to start off with, then 16
    flags = int.from_bytes(buffer[offset:offset + 2], byteorder="little")
    offset += 2
    flags >>= 8
    outputoffset = 0 # u16
    def getflag():
        nonlocal bits
        nonlocal flags
        nonlocal offset

        if bits == 0:
            slice_ = buffer[offset:offset + 2]
            if len(slice_) < 2:
                raise Exception("Out of data")
            flags = int.from_bytes(slice_, byteorder="little")
            offset += 2
            bits = 16
        flag = flags & 1
        flags >>= 1
        bits -= 1
        return flag
    def setup_run(prev_u_buffer_pos):
        nonlocal offset
        nonlocal buffer
        nonlocal output
        nonlocal outputoffset

        run = 2 # u16
        if getflag() == 0:
            run += 1
            if getflag() == 0:
                run += 1
                if getflag() == 0:
                    run += 1
                    if getflag() == 0:
                        if getflag() == 0:
                            slice_ = buffer[offset:offset + 1]
                            if len(slice_) < 1:
                                raise Exception("Out of data")
                            run = int.from_bytes(slice_, byteorder="little")
                            offset += 1
                            run += 0xE
                        else:
                            run = 0
                            for i in range(3):
                                run = (run << 1) | getflag()
                            run += 0x6
        # Does the 'copy from buffer' thing
        for i in range(run):
            output[outputoffset] = output[outputoffset - prev_u_buffer_pos]
            outputoffset += 1
    while True:
        if getflag() != 0: # Call next method to process next flag
            if getflag() != 0: # Long look-back distance or exit program or repeating sequence (flags = 11)
                run = 0 # u16
                for i in range(5): # Load high-order distance from flags (max = 0x31)
                    run = (run << 1) | getflag()
                prev_u_buffer_pos = int.from_bytes(buffer[offset:offset + 1], byteorder="little") # Load low-order distance (max = 0xFF)
                                                                                                                   # Also acts as flag byte
                                                                                                                   # run = 0 and byte = 0 -> exit program
                                                                                                                   # run = 0 and byte = 1 -> sequence of repeating bytes
                offset += 1
                if run != 0:
                    prev_u_buffer_pos = prev_u_buffer_pos | (run << 8) # Add high and low order distance (max distance = 0x31FF)
                    setup_run(prev_u_buffer_pos) # Get run length and finish unpacking (write to output)
                elif prev_u_buffer_pos > 2: # Is this used? Seems inefficient.
                    setup_run(prev_u_buffer_pos)
                elif prev_u_buffer_pos == 0: # Decompression complete. End program.
                    break
                else: # Repeating byte
                    branch = getflag() # True = long repeating sequence (> 30)
                    for i in range(4):
                        run = (run << 1) | getflag()
                    if branch != 0:
                        run = (run << 0x8) | int.from_bytes(buffer[offset:offset + 1], byteorder="little")  # Load run length from byte and add high-order run length (max = 0xFFF + 0xE)
                        offset += 1
                    run += 0xE
                    output[outputoffset:outputoffset + run] = bytes(buffer[offset:offset + 1]) * run
                    offset += 1
                    outputoffset += run
            else: # Short look-back distance (flags = 10)
                prev_u_buffer_pos = int.from_bytes(buffer[offset:offset + 1], byteorder="little") # Get the look-back distance (max = 0xFF)
                offset += 1
                setup_run(prev_u_buffer_pos) # Get run length and finish unpacking (write to output)
        else: # Copy byte (flags = 0)
            output[outputoffset:outputoffset + 1] = buffer[offset:offset + 1]
            outputoffset += 1
            offset += 1
    return outputoffset, offset

def parse_data_blocks (f):
    # Larger data blocks are segmented prior to compression, not really sure what the rules are here
    # compressed_size and segment_size are 8 bytes larger than block_size for header?  uncompressed_size is true
    # size without any padding, as is uncompressed_block_size
    flags, = struct.unpack("<I", f.read(4))
    if flags & 0x80000000:
        num_blocks, compressed_size, segment_size, uncompressed_size = struct.unpack("<4I", f.read(16))
        data = bytes()
        for i in range(num_blocks):
            block_size, uncompressed_block_size, block_type = struct.unpack("<3I", f.read(12))
            is_compressed = (block_type == 8)
            data += parse_data_block_new(f, block_size, is_compressed)
    else: # Thank you to uyjulian, source: https://gist.github.com/uyjulian/a6ba33dc29858327ffa0db57f447abe5
        dst_offset = 0
        compressed_size = flags
        uncompressed_size, num_blocks = struct.unpack("<2I", f.read(8))
        dst = bytearray(uncompressed_size) # Should already be initialized with 0
        cdata = io.BytesIO(f.read(compressed_size - 8))
        for i in range(num_blocks):
            block_size = struct.unpack("<H", cdata.read(2))[0]
            output_tmp = bytearray(65536)
            inbuf = cdata.read(block_size - 2)
            if inbuf[0] != 0:
                raise Exception("Non-zero method currently not supported")
            num1, num2 = decompress(inbuf, output_tmp, block_size)
            dst[dst_offset:dst_offset + num1] = output_tmp[0:num1]
            dst_offset += num1
            if dst_offset >= uncompressed_size:
                break
            x = cdata.read(1)
            if len(x) == 0:
                break
            if x[0] == 0:
                break
        data = bytes(dst)
    return(data)

def parse_info_block (f):
    return {'name': f.read(64).split(b'\x00')[0].decode('ASCII'),\
        'matrix': [list(struct.unpack("<4f", f.read(16))) for x in range(4)],\
        'v0': list(struct.unpack("<3f", f.read(12)))}

def parse_rty2_block (f):
    return {'material_variant': struct.unpack("<I", f.read(4))[0],\
        'unknown': struct.unpack("<B", f.read(1))[0],\
        'v0': list(struct.unpack("<3f", f.read(12)))}

def parse_lig3_block (f):
    return {'v0': list(struct.unpack("<4f", f.read(16))),\
        'unknown': struct.unpack("<B", f.read(1))[0],\
        'unknown2': struct.unpack("<f", f.read(4))[0],\
        'v1': list(struct.unpack("<4f", f.read(16)))}

def parse_infz_block (f):
    return {'v0': list(struct.unpack("<4f", f.read(16)))}

def parse_bbox_block (f):
    return {'a': list(struct.unpack("<3f", f.read(12))),\
        'b': list(struct.unpack("<3f", f.read(12))),\
        'c': list(struct.unpack("<3f", f.read(12))),\
        'd': list(struct.unpack("<3f", f.read(12)))}

def parse_chid_block (f):
    block = {}
    block['parent'] = f.read(64).split(b'\x00')[0].decode('ASCII')
    num_children, = struct.unpack("<I", f.read(4))
    block['children'] = [f.read(64).split(b'\x00')[0].decode('ASCII') for x in range(num_children)]
    return(block)

def parse_jntv_block (f):
    return {'v0': list(struct.unpack("<4f", f.read(16))),\
        'id': struct.unpack("<I", f.read(4))[0]}

def parse_mat6_block (f):
    count, = struct.unpack("<I", f.read(4))
    mat_blocks = []
    for i in range(count):
        segment_length, = struct.unpack("<I", f.read(4))
        data = parse_data_blocks(f)
        with io.BytesIO(data) as block:
            magic = block.read(4).decode('ASCII')
            flags, part_size = struct.unpack("<2I", block.read(8))
            block.seek(28,1)
            count_parameters, = struct.unpack("<I", block.read(4))
            block.seek(4,1)
            count_textures, = struct.unpack("<I", block.read(4))
            parameters = []
            for j in range(count_parameters):
                parameters.append(list(struct.unpack("<4f", block.read(16))))
            textures_flags = []
            for j in range(count_textures):
                textures_flags.append(list(struct.unpack("<7H", block.read(14))))
            block.seek(part_size,0)
            mate_magic = block.read(4).decode('ASCII')
            mate_flags, mate_part_size, name_len = struct.unpack("<3I", block.read(12))
            current_mat_name = block.read(name_len).split(b'\x00')[0].decode('ASCII')
            name_len, = struct.unpack("<I", block.read(4))
            textures = []
            for j in range(count_textures):
                textures.append({'name': block.read(name_len).split(b'\x00')[0].decode('ASCII'),\
                    'flags': textures_flags[j]})
        mat_blocks.append({'MATM_flags': flags, 'MATE_flags': mate_flags,\
            'parameters': parameters, 'textures': textures})
    return(mat_blocks)

def parse_bon3_block (f):
    int0, = struct.unpack("<I", f.read(4))
    mesh_name = f.read(64).split(b'\x00')[0].decode('ASCII')
    int1, = struct.unpack("<I", f.read(4))
    matm = []
    for i in range(3):
        matm.append(parse_data_blocks(f))
    addr_bone = 0
    joints = []
    while (addr_bone < len(matm[0])):
        name = matm[0][addr_bone:addr_bone+64].split(b'\x00')[0].decode('ASCII')
        if not name == '':
            joints.append(name)
        addr_bone += 64
    addr_bone = 0
    bones = []
    while (addr_bone < len(matm[1])):
        name = matm[1][addr_bone:addr_bone+64].split(b'\x00')[0].decode('ASCII')
        if not name == '':
            offset_mat = [list(struct.unpack("<4f", matm[2][addr_bone:addr_bone+16])),\
                list(struct.unpack("<4f", matm[2][addr_bone+16:addr_bone+32])),\
                list(struct.unpack("<4f", matm[2][addr_bone+32:addr_bone+48])),\
                list(struct.unpack("<4f", matm[2][addr_bone+48:addr_bone+64]))]
            bones.append({'name': name, 'offset_mat': offset_mat})
        addr_bone += 64
    return({'mesh_name': mesh_name, 'joints': joints, 'bones': bones})

# Thank you to Kyuuhachi for partially reversing VPA8 and sharing his findings with me!
def parse_vpa8_block (f):
    count, size1, size2 = struct.unpack("<3I", f.read(12))
    with io.BytesIO(parse_data_blocks(f)) as ff:
        p_arr_v = [struct.unpack("<4f4I8f13I", ff.read(116)) for i in range(count)]
    buffer_v = b''.join([parse_data_blocks(f) for i in range(math.ceil(size1 / 0x40000))]) # len(data1) == size1
    with io.BytesIO(parse_data_blocks(f)) as ff:
        p_arr_i = [struct.unpack("<3I", ff.read(12)) for i in range(count)]
    buffer_i = b''.join([parse_data_blocks(f) for i in range(math.ceil(size2 / 0x40000))]) # len(data2) * 2 == size2
    fmt_struct = make_vpa8_fmt()
    section_info = []
    mesh_buffers = []
    pointer_v = 0
    pointer_i = 0
    for i in range(count):
        mesh = {}
        mesh["header"] = { 'center': p_arr_v[i][0:4], 'v_unk0': p_arr_v[i][4], 'material': p_arr_v[i][5],\
            'v_unk1': p_arr_v[i][6], 'num_vertices': p_arr_v[i][7], 'min': p_arr_v[i][8:12],\
            'max': p_arr_v[i][12:16], 'v_unk3': p_arr_v[i][16:20], 'bone_palette': p_arr_v[i][20:29],\
            'i_unk0': p_arr_i[i][0], 'num_indices': p_arr_i[i][1], 'i_unk1': p_arr_i[i][2] }
        mesh["material_id"] = mesh["header"]["material"]
        mesh["block_size"] = fmt_struct['stride']
        mesh["vertex_count"] = mesh["header"]["num_vertices"]
        ib = read_ib_stream(buffer_i[pointer_i:pointer_i+mesh["header"]["num_indices"]*2], fmt_struct)
        vb = read_vb_stream(buffer_v[pointer_v:pointer_v+mesh["header"]["num_vertices"]*40], fmt_struct)
        # Map bone palette to mesh global indices
        to_global = [0] + list(mesh["header"]['bone_palette'])
        for j in range(len(vb[4]['Buffer'])):
            vb[4]['Buffer'][j] = [to_global[x]//3 for x in vb[4]['Buffer'][j]]
        section_info.append(mesh)
        mesh_buffers.append({'fmt': fmt_struct, 'ib': ib, 'vb': vb})
        pointer_i += mesh["header"]["num_indices"]*2
        pointer_v += mesh["header"]["num_vertices"]*40
    return(section_info, mesh_buffers)

def parse_vpax_block (f, block_type, trim_for_gpu = False):
    count, = struct.unpack("<I", f.read(4))
    indices = []
    vertices = []
    mesh_buffers = []
    for i in range(count):
        print("Decompressing vertex buffer {0}".format(i))
        size, = struct.unpack("<I", f.read(4))
        blocks = 1
        if block_type == 'VPA9':
            blocks = math.ceil(size / 0x40000)
        data = b''.join([parse_data_blocks(f) for i in range(blocks)])
        vertices.append(data)
    for i in range(count):
        print("Decompressing index buffer {0}".format(i))
        size, = struct.unpack("<I", f.read(4))
        blocks = 1
        if block_type == 'VPA9':
            blocks = math.ceil(size / 0x40000)
        data = b''.join([parse_data_blocks(f) for i in range(blocks)])
        indices.append(data)
    section_info = []
    for i in range(count):
        with io.BytesIO(vertices[i]) as vb_stream:
            mesh = {}
            mesh["header"] = {'name': vb_stream.read(4).decode('ASCII'), 'version': struct.unpack("<I", vb_stream.read(4))[0],\
                'v0': struct.unpack("<4f", vb_stream.read(16)), 'v1': struct.unpack("<4f", vb_stream.read(16)),\
                'v2': struct.unpack("<4f", vb_stream.read(16)), 'uint0': struct.unpack("<77I", vb_stream.read(308))}
            if mesh["header"]["name"] == 'VPAC':
                fmt_struct = make_fmt(mesh["header"]["uint0"][2], game_version = {'VPA9':1, 'VPAX':1, 'VP11':2}[block_type])
                mesh["material_id"] = mesh["header"]["uint0"][68]
                mesh["block_size"] = fmt_struct['stride']
                mesh["vertex_count"] = mesh["header"]["uint0"][0]
                #vb = vb_stream.read(mesh["block_size"] * mesh["vertex_count"])
                vb = read_vb_stream(vb_stream.read(), fmt_struct, e = '<')
                ib = read_ib_stream(indices[i], fmt_struct, e = '<')
                if trim_for_gpu == True and fmt_struct['stride'] == '160':
                    mesh_buffers.append({'fmt': make_88_fmt(), 'ib': ib,\
                        'vb': [vb[i] for i in [0,1,4,5,6,7,8,9,12,14]]})
                else:
                    mesh_buffers.append({'fmt': fmt_struct, 'ib': ib, 'vb': vb})
            section_info.append(mesh)
    return(section_info, mesh_buffers)

def obtain_mesh_data (f, it3_contents, it3_filename, trim_for_gpu = False):
    vpax_blocks = [i for i in range(len(it3_contents)) if it3_contents[i]['type'] in ['VPA8', 'VPA9', 'VPAX', 'VP11']]
    meshes = []
    for i in range(len(vpax_blocks)):
        print("Processing section {0}".format(it3_contents[vpax_blocks[i]]['info_name']))
        f.seek(it3_contents[vpax_blocks[i]]['section_start_offset'])
        if it3_contents[vpax_blocks[i]]['type'] == 'VPA8':
            it3_contents[vpax_blocks[i]]["data"], mesh_data = parse_vpa8_block(f)
            node_list = [it3_contents[vpax_blocks[i]]['info_name']]
        else:
            it3_contents[vpax_blocks[i]]["data"], mesh_data = parse_vpax_block(f, it3_contents[vpax_blocks[i]]['type'], trim_for_gpu)
            # For some reason Ys VIII starts numbering at 1 (root is node 1, not node 0)
            node_list = [it3_filename[:-4]]
        bone_section = [x for x in it3_contents if x['type'] == 'BON3'\
            and x['info_name'] == it3_contents[vpax_blocks[i]]['info_name']]
        if len(bone_section) > 0:
            node_list.extend(bone_section[0]['data']['joints'])
        meshes.append({'name': it3_contents[vpax_blocks[i]]['info_name'], 'meshes': mesh_data,\
            'node_list': node_list})
    return(it3_contents, meshes)

def write_fmt_ib_vb (mesh_buffer, filename, node_list = [], complete_maps = False):
    print("Writing submesh {0}".format(filename))
    write_fmt(mesh_buffer['fmt'], filename + '.fmt')
    write_ib(mesh_buffer['ib'], filename +  '.ib', mesh_buffer['fmt'])
    write_vb(mesh_buffer['vb'], filename +  '.vb', mesh_buffer['fmt'])
    if len(node_list) > 0:
        # Find vertex groups referenced by vertices so that we can cull the empty ones
        active_nodes = list(set(list(chain.from_iterable([x["Buffer"] for x in mesh_buffer["vb"] \
            if x["SemanticName"] == 'BLENDINDICES'][0]))))
        vgmap_json = {}
        for i in range(len(node_list)):
            if (i in active_nodes) or (complete_maps == True):
                vgmap_json[node_list[i]] = i
        with open(filename + '.vgmap', 'wb') as f:
            f.write(json.dumps(vgmap_json, indent=4).encode("utf-8"))
    return

def dds_header (dwHeight, dwWidth, dwPitchOrLinearSize):
    header_info = {'dwSize': 124, 'dwFlags': 0xA1007, 'dwHeight': dwHeight,\
        'dwWidth': dwWidth, 'dwPitchOrLinearSize': dwPitchOrLinearSize,\
        'dwDepth': 1, 'dwMipMapCount': 1, 'pixel_format': {'dwSize': 32,\
        'dwFlags': 0x4, 'dwFourCC': 'DX10', 'dwRGBBitCount': 0, 'dwRBitMask': 0,\
        'dwGBitMask': 0, 'dwBBitMask': 0, 'dwABitMask': 0}, 'dwCaps': 0x1000,\
        'dwCaps2': 0, 'dwCaps3': 0, 'dwCaps4': 0, 'dxt10_header':\
        {'dxgiFormat': 98, 'resourceDimension': 3, 'miscFlag': 0, 'arraySize': 1, 'miscFlags2': 0}}
    header = b'DDS ' + struct.pack("<18I", *([header_info['dwSize'], header_info['dwFlags'],\
        header_info['dwHeight'], header_info['dwWidth'], header_info['dwPitchOrLinearSize'],\
        header_info['dwDepth'], header_info['dwMipMapCount']] + [0 for x in range(11)]))
    header += struct.pack("<2I", header_info["pixel_format"]['dwSize'], header_info["pixel_format"]['dwFlags'])
    header += header_info["pixel_format"]['dwFourCC'].encode()
    header += struct.pack("<5I", header_info["pixel_format"]['dwRGBBitCount'], header_info["pixel_format"]['dwRBitMask'],\
        header_info["pixel_format"]['dwGBitMask'], header_info["pixel_format"]['dwBBitMask'],\
        header_info["pixel_format"]['dwABitMask'])
    header += struct.pack("<5I", header_info['dwCaps'], header_info['dwCaps2'], header_info['dwCaps3'],\
        header_info['dwCaps4'], 0)
    header += struct.pack("<5I", header_info['dxt10_header']['dxgiFormat'], header_info['dxt10_header']['resourceDimension'],\
        header_info['dxt10_header']['miscFlag'], header_info['dxt10_header']['arraySize'],\
        header_info['dxt10_header']['miscFlags2'])
    return(header)

# Like everything else in this script, adapted from TwnKey's work.  TwnKey credits GFD studio.
def morton (t, sx, sy):
    num = [1,1,t,sx,sy,0,0]
    while num[3] > 1 or num[4] > 1:
        if num[3] > 1:
            num[5] += num[1] * (num[2] & 1)
            num[2] >>= 1
            num[1] *= 2
            num[3] >>= 1
        if num[4] > 1:
            num[6] += num[0] * (num[2] & 1)
            num[2] >>= 1
            num[0] *= 2
            num[4] >>= 1
    return(num[6] * sx + num[5])

def unswizzle (texture_data, dwHeight, dwWidth, block_size):
    morton_seq = [morton(x,8,8) for x in range(64)]
    output = bytearray(dwHeight * dwWidth)
    data_index = 0
    for y in range(((dwHeight // 4) + 7) // 8):
        for x in range(((dwWidth // 4) + 7) // 8):
            for t in range(64):
                y_offset = (y * 8) + (morton_seq[t] // 8)
                x_offset = (x * 8) + (morton_seq[t] % 8)
                if (x_offset < dwWidth // 4) and (y_offset < dwHeight // 4):
                    dest_index = block_size * (y_offset * (dwWidth // 4) + x_offset)
                    output[dest_index:dest_index+block_size] = texture_data[data_index:data_index+block_size]
                data_index += block_size
    return(output)

def parse_texi_block (f):
    section_info = []
    valid_bpps = [0,1,2,4,5,6,7,8,10]
    bpp_multipliers = {0:8,1:8,2:8,4:0x10,5:0x20,6:4,7:8,8:8,10:8}
    texture_data = bytes()
    if f.read(4) == b'ITP\xff':
        while True:
            section = {"type": f.read(4).decode('ASCII')}
            size, = struct.unpack("<I", f.read(4))
            if section["type"] == 'IHDR':
                section["data"] = {}
                section["data"]["unk0"], section["data"]["dim1"], section["data"]["dim2"],\
                    section["data"]["compressed_size"], section["data"]["s1"], section["data"]["bpp"],\
                    section["data"]["s3"], section["data"]["s4"], section["data"]["type"],\
                    section["data"]["s6"], section["data"]["unk1"] = struct.unpack("<4I6HI", f.read(32))
            elif section["type"] == 'IALP':
                section["data"] = list(struct.unpack("<2I", f.read(8)))
            elif section["type"] == 'IMIP':
                section["data"] = list(struct.unpack("<3I", f.read(12)))
            elif section["type"] == 'IHAS':
                section["data"] = list(struct.unpack("<2I2f", f.read(16)))
            elif section["type"] == 'IDAT':
                section["data"] = {}
                section["data"]["unk0"], section["data"]["unk1"] = struct.unpack("<2I", f.read(8))
                ihdr = [x for x in section_info if x['type'] == 'IHDR']
                if len(ihdr) > 0:
                    if ((ihdr[0]['data']['type'] & 0xFFFFFF00) | (ihdr[0]['data']['type'] == 2)):
                        section["data"]["bug_report"] = 'Not expected in TwnKey\'s code'
                        section["data"]["unk2"], section["data"]["unk3"] = struct.unpack("<2I", f.read(8))
                        texture_data = parse_data_blocks(f)
                    else:
                        if ihdr[0]['data']['type'] in [1,2,3]:
                            texture_data = parse_data_blocks(f)
                        elif ihdr[0]['data']['bpp'] in valid_bpps:
                            texture_data = f.read(bpp_multipliers[ihdr[0]['data']['bpp']] * ihdr[0]['data']['dim1'] * ihdr[0]['data']['dim2'])
                        else:
                            f.seek(size-8,1)
                else:
                    f.seek(size-8,1)
            elif section["type"] == 'IEND':
                break
            else:
                f.seek(size,1)
            section_info.append(section)
        if len(texture_data) > 0:
            texture = dds_header(ihdr[0]['data']['dim1'], ihdr[0]['data']['dim2'], len(texture_data)) +\
                unswizzle(texture_data, ihdr[0]['data']['dim1'], ihdr[0]['data']['dim2'], 16)
        else:
            texture = b''
    else:
        texture = b''
    return(section_info, texture)

def obtain_textures (f, it3_contents):
    texi_blocks = [i for i in range(len(it3_contents)) if it3_contents[i]['type'] in ['TEXI', 'TEX2']]
    textures = []
    for i in range(len(texi_blocks)):
        f.seek(it3_contents[texi_blocks[i]]['section_start_offset'])
        if it3_contents[texi_blocks[i]]['type'] == 'TEXI':
            it3_contents[texi_blocks[i]]['texture_name'] = f.read(36).split(b'\x00')[0].decode('ASCII')
        else: #'TEX2'
            f.seek(4,1) #unk int
            name = f.read(1)
            while not name[-1:] == b'\x00':
                name += f.read(1)
            it3_contents[texi_blocks[i]]['texture_name'] = name.rstrip(b'\x00').decode('ASCII')
        print("Processing texture {0}".format(it3_contents[texi_blocks[i]]['texture_name']))
        start_offset = f.tell()
        it3_contents[texi_blocks[i]]["data"], texture = parse_texi_block(f)
        if len(texture) == 0:
            f.seek(start_offset)
            texture = f.read(it3_contents[texi_blocks[i]]['size'] - (start_offset - it3_contents[texi_blocks[i]]['section_start_offset']))
        textures.append({'name': it3_contents[texi_blocks[i]]['texture_name'], 'texture': texture})
    return(it3_contents, textures)

def parse_it3 (f):
    file_length = f.seek(0,2)
    f.seek(0,0)
    contents = []
    info_section = ''
    while f.tell() < file_length:
        current_offset = f.tell()
        section_info = {}
        section_info["type"] = f.read(4).decode('ASCII')
        section_info["size"], = struct.unpack("<I",f.read(4))
        section_info["section_start_offset"] = f.tell()
        if section_info["type"] == 'INFO':
            section_info["data"] = parse_info_block(f)
            info_section = section_info["data"]["name"]
        else:
            section_info["info_name"] = info_section
        if section_info["type"] == 'RTY2':
            section_info["data"] = parse_rty2_block(f)
        elif section_info["type"] == 'LIG3':
            section_info["data"] = parse_lig3_block(f)
        elif section_info["type"] == 'INFZ':
            section_info["data"] = parse_infz_block(f)
        elif section_info["type"] == 'BBOX':
            section_info["data"] = parse_bbox_block(f)
        elif section_info["type"] == 'CHID':
            section_info["data"] = parse_chid_block(f)
        elif section_info["type"] == 'JNTV':
            section_info["data"] = parse_jntv_block(f)
        elif section_info["type"] == 'MAT6':
            section_info["data"] = parse_mat6_block(f)
        elif section_info["type"] == 'BON3':
            section_info["data"] = parse_bon3_block(f)
        contents.append(section_info)
        f.seek(section_info["section_start_offset"] + section_info["size"], 0) # Move forward to the next section
    return(contents)

def process_it3 (it3_filename, complete_maps = complete_vgmaps_default, trim_for_gpu = False, overwrite = False):
    print("Processing {0}".format(it3_filename))
    if os.path.exists(it3_filename[:-4]) and (os.path.isdir(it3_filename[:-4])) and (overwrite == False):
        if str(input(it3_filename[:-4] + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(it3_filename[:-4]):
        with open(it3_filename, 'rb') as f:
            it3_contents = parse_it3(f)
            it3_contents, meshes = obtain_mesh_data(f, it3_contents, it3_filename, trim_for_gpu = trim_for_gpu)
            it3_contents, textures = obtain_textures(f, it3_contents)
            if not os.path.exists(it3_filename[:-4]):
                os.mkdir(it3_filename[:-4])
        with open(it3_filename[:-4] + '/container_info.json', 'wb') as f:
            f.write(json.dumps(it3_contents, indent=4).encode("utf-8"))
        if not os.path.exists(it3_filename[:-4] + '/meshes'):
            os.mkdir(it3_filename[:-4] + '/meshes')
        for i in range(len(meshes)):
            for j in range(len(meshes[i]["meshes"])):
                safe_filename = "".join([x if x not in "\/:*?<>|" else "_" for x in meshes[i]["name"]])
                write_fmt_ib_vb(meshes[i]["meshes"][j], it3_filename[:-4] +\
                    '/meshes/{0}_{1:02d}'.format(safe_filename, j),\
                    node_list = meshes[i]["node_list"], complete_maps = complete_maps)
        if not os.path.exists(it3_filename[:-4] + '/textures'):
            os.mkdir(it3_filename[:-4] + '/textures')
        print("Writing textures")
        for i in range(len(textures)):
            safe_filename = "".join([x if x not in "\/:*?<>|" else "_" for x in textures[i]["name"]])
            if textures[i]["texture"][0:4] == b'DDS ':
                with open(it3_filename[:-4] + '/textures/{0}.dds'.format(safe_filename), 'wb') as f:
                    f.write(textures[i]["texture"])
            else:
                with open(it3_filename[:-4] + '/textures/{0}.itp'.format(safe_filename), 'wb') as f:
                    f.write(textures[i]["texture"])
    return

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        if complete_vgmaps_default == True:
            parser.add_argument('-p', '--partialmaps', help="Provide vgmaps with non-empty groups only", action="store_false")
        else:
            parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire mesh skeleton", action="store_true")
        parser.add_argument('-t', '--trim_for_gpu', help="Trim vertex buffer for GPU injection (3DMigoto)", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('it3_filename', help="Name of it3 file to export from (required).")
        args = parser.parse_args()
        if complete_vgmaps_default == True:
            complete_maps = args.partialmaps
        else:
            complete_maps = args.completemaps
        if os.path.exists(args.it3_filename) and args.it3_filename[-4:].lower() == '.it3':
            process_it3(args.it3_filename, complete_maps = complete_maps, trim_for_gpu = args.trim_for_gpu, overwrite = args.overwrite)
    else:
        it3_files = glob.glob('*.it3')
        for i in range(len(it3_files)):
            process_it3(it3_files[i])
