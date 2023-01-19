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

import struct, base64, io, json, os, sys, glob
from itertools import chain
from lib_fmtibvb import *

def make_160_fmt():
    return({'stride': '160', 'topology': 'trianglelist', 'format': 'DXGI_FORMAT_R16_UINT',\
        'elements': [{'id': '0', 'SemanticName': 'POSITION', 'SemanticIndex': '0',\
        'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '0',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '1',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '0', 'Format': 'R32G32B32A32_FLOAT',\
        'InputSlot': '0', 'AlignedByteOffset': '16', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '2', 'SemanticName': 'UNKNOWN', 'SemanticIndex': '1',\
        'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '32',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '3',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '2', 'Format': 'R32G32B32A32_FLOAT',\
        'InputSlot': '0', 'AlignedByteOffset': '48', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '4', 'SemanticName': 'NORMAL', 'SemanticIndex': '0',\
        'Format': 'R8G8B8A8_SNORM', 'InputSlot': '0', 'AlignedByteOffset': '64',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '5',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '3', 'Format': 'R8G8B8A8_SNORM',\
        'InputSlot': '0', 'AlignedByteOffset': '68', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '6', 'SemanticName': 'COLOR', 'SemanticIndex': '0',\
        'Format': 'R8G8B8A8_UNORM', 'InputSlot': '0', 'AlignedByteOffset': '72',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '7',\
        'SemanticName': 'COLOR', 'SemanticIndex': '1', 'Format': 'R8G8B8A8_UNORM',\
        'InputSlot': '0', 'AlignedByteOffset': '76', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '8', 'SemanticName': 'TEXCOORD', 'SemanticIndex': '0',\
        'Format': 'R32G32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '80',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '9',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '4', 'Format': 'R32G32_FLOAT',\
        'InputSlot': '0', 'AlignedByteOffset': '88', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '10', 'SemanticName': 'TEXCOORD', 'SemanticIndex': '1',\
        'Format': 'R32G32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '96',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '11',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '5', 'Format': 'R32G32_FLOAT',\
        'InputSlot': '0', 'AlignedByteOffset': '104', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '12', 'SemanticName': 'UNKNOWN', 'SemanticIndex': '6',\
        'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '112',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '13',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '7', 'Format': 'R32G32B32A32_FLOAT',\
        'InputSlot': '0', 'AlignedByteOffset': '128', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '14', 'SemanticName': 'BLENDWEIGHTS', 'SemanticIndex': '0',\
        'Format': 'R8G8B8A8_UNORM', 'InputSlot': '0', 'AlignedByteOffset': '144',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '15',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '8', 'Format': 'R8G8B8A8_UNORM',\
        'InputSlot': '0', 'AlignedByteOffset': '148', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '16', 'SemanticName': 'BLENDINDICES', 'SemanticIndex': '0',\
        'Format': 'R8G8B8A8_UINT', 'InputSlot': '0', 'AlignedByteOffset': '152',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '17',\
        'SemanticName': 'UNKNOWN', 'SemanticIndex': '9', 'Format': 'R8G8B8A8_UINT',\
        'InputSlot': '0', 'AlignedByteOffset': '156', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}]})

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
        'SemanticIndex': '0', 'Format': 'R32G32_FLOAT', 'InputSlot': '0',\
        'AlignedByteOffset': '48', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '7', 'SemanticName': 'UNKNOWN',\
        'SemanticIndex': '2', 'Format': 'R32G32_FLOAT', 'InputSlot': '0',\
        'AlignedByteOffset': '56', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'},\
        {'id': '8', 'SemanticName': 'TEXCOORD', 'SemanticIndex': '1', 'Format': 'R32G32_FLOAT',\
        'InputSlot': '0', 'AlignedByteOffset': '64', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '9', 'SemanticName': 'UNKNOWN', 'SemanticIndex': '3',\
        'Format': 'R32G32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '72',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}, {'id': '10',\
        'SemanticName': 'BLENDWEIGHTS', 'SemanticIndex': '0', 'Format': 'R8G8B8A8_UNORM',\
        'InputSlot': '0', 'AlignedByteOffset': '80', 'InputSlotClass': 'per-vertex',\
        'InstanceDataStepRate': '0'}, {'id': '11', 'SemanticName': 'BLENDINDICES',\
        'SemanticIndex': '0', 'Format': 'R8G8B8A8_UINT', 'InputSlot': '0',\
        'AlignedByteOffset': '84', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}]})

def parse_data_block (f, block_size, is_compressed):
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

def parse_data_blocks (f):
    # Larger data blocks are segmented prior to compression, not really sure what the rules are here
    # compressed_size and segment_size are 8 bytes larger than block_size for header?  uncompressed_size is true
    # size without any padding, as is uncompressed_block_size
    flags, num_blocks, compressed_size, segment_size, uncompressed_size = struct.unpack("<5I", f.read(20))
    data = bytes()
    for i in range(num_blocks):
        block_size, uncompressed_block_size, block_type = struct.unpack("<3I", f.read(12))
        is_compressed = (block_type == 8)
        data += parse_data_block(f, block_size, is_compressed)
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

def parse_vpax_block (f, trim_for_gpu = False, game_version = 1):
    count, = struct.unpack("<I", f.read(4))
    indices = []
    vertices = []
    mesh_buffers = []
    fmt_struct = make_160_fmt()
    if game_version == 2:
        fmt_struct["format"] = "DXGI_FORMAT_R32_UINT"
    for i in range(count):
        print("Decompressing vertex buffer {0}".format(i))
        size, = struct.unpack("<I", f.read(4))
        data = parse_data_blocks(f)
        vertices.append(data)
    for i in range(count):
        print("Decompressing index buffer {0}".format(i))
        size, = struct.unpack("<I", f.read(4))
        data = parse_data_blocks(f)
        indices.append(data)
    section_info = []
    for i in range(count):
        with io.BytesIO(vertices[i]) as vb_stream:
            mesh = {}
            mesh["header"] = {'name': vb_stream.read(4).decode('ASCII'), 'version': struct.unpack("<I", vb_stream.read(4))[0],\
                'v0': struct.unpack("<4f", vb_stream.read(16)), 'v1': struct.unpack("<4f", vb_stream.read(16)),\
                'v2': struct.unpack("<4f", vb_stream.read(16)), 'uint0': struct.unpack("<77I", vb_stream.read(308))}
            if mesh["header"]["name"] == 'VPAC':
                mask, count, uVar1, iVar4, local_c = mesh["header"]["uint0"][2], 0x10, 1, 0, 0
                while True: # Measure total stride (iVar4) by looking at the bits in the mask
                    if ((mask & uVar1) != 0):
                        if uVar1 in [1, 2, 4, 8, 0x100, 0x200, 0x400, 0x800]:
                            iVar4 += 0x10 # Add 16 to the stride if bit is 1
                            local_c += 1
                        elif uVar1 in [0x10, 0x20, 0x40, 0x80, 0x1000, 0x2000, 0x4000, 0x8000]:
                            iVar4 += 4 # Add 4 to the stride if bit is 1
                            local_c += 1
                    uVar1 = uVar1 << 1 | int(uVar1 <0) # Bit-shifting 1, 2, 4, 8, 16, 32, etc total 16 times
                    count -= 1
                    if count == 0:
                        break
                count1 = local_c # Number of positive bits
                count2 = mesh["header"]["uint0"][0] # Vertex count
                mesh["material_id"] = mesh["header"]["uint0"][68]
                mesh["block_size"] = iVar4 # Not sure why we did this, since it seems stride is always 160?
                mesh["vertex_count"] = mesh["header"]["uint0"][0]
                #vb = vb_stream.read(mesh["block_size"] * mesh["vertex_count"])
                vb = read_vb_stream(vb_stream.read(), fmt_struct, e = '<')
                ib = read_ib_stream(indices[i], fmt_struct, e = '<')
                if trim_for_gpu == False:
                    mesh_buffers.append({'fmt': fmt_struct, 'ib': ib, 'vb': vb})
                else:
                    mesh_buffers.append({'fmt': make_88_fmt(), 'ib': ib,\
                        'vb': [vb[i] for i in [0,1,4,5,6,7,8,9,10,11,14,16]]})
            section_info.append(mesh)
    return(section_info, mesh_buffers)

def write_fmt_ib_vb (mesh_buffer, filename, node_list = False, complete_maps = False):
    print("Processing submesh {0}...".format(filename))
    write_fmt(mesh_buffer['fmt'], filename + '.fmt')
    write_ib(mesh_buffer['ib'], filename +  '.ib', mesh_buffer['fmt'])
    write_vb(mesh_buffer['vb'], filename +  '.vb', mesh_buffer['fmt'])
    if not node_list == False:
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
    return(section_info, texture)

def process_it3 (it3_name, complete_maps = False, trim_for_gpu = False, overwrite = False):
    if os.path.exists(it3_name[:-4]) and (os.path.isdir(it3_name[:-4])) and (overwrite == False):
        if str(input(it3_name[:-4] + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(it3_name[:-4]):
        with open(it3_name, 'rb') as f:
            print("Processing {0}".format(it3_name))
            file_length = f.seek(0,2)
            f.seek(0,0)
            contents = []
            info_section = ''
            meshes = []
            textures = []
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
                elif section_info["type"] == 'VPAX':
                    print("Processing section {0}".format(info_section))
                    section_info["data"], mesh_data = parse_vpax_block(f, trim_for_gpu = trim_for_gpu)
                    meshes.append({'name': info_section, 'meshes': mesh_data})
                elif section_info["type"] == 'TEXI':
                    section_info['texture_name'] = f.read(36).split(b'\x00')[0].decode('ASCII')
                    print("Processing texture {0}".format(section_info['texture_name']))
                    section_info["data"], texture = parse_texi_block(f)
                    textures.append({'name': section_info['texture_name'], 'texture': texture})
                contents.append(section_info)
                f.seek(section_info["section_start_offset"] + section_info["size"], 0) # Move forward to the next section
        if not os.path.exists(it3_name[:-4]):
            os.mkdir(it3_name[:-4])
        with open(it3_name[:-4] + '/container_info.json', 'wb') as f:
            f.write(json.dumps(contents, indent=4).encode("utf-8"))
        if not os.path.exists(it3_name[:-4] + '/meshes'):
            os.mkdir(it3_name[:-4] + '/meshes')
        for i in range(len(meshes)):
            for j in range(len(meshes[i]["meshes"])):
                bone_section = [x for x in contents if x['type'] == 'BON3' and x['info_name'] == meshes[i]["name"]]
                if len(bone_section) > 0:
                    # For some reason Ys VIII starts numbering at 1 (root is node 1, not node 0)
                    node_list = [meshes[i]["name"]] + bone_section[0]['data']['joints']
                else:
                    node_list = False
                write_fmt_ib_vb(meshes[i]["meshes"][j], it3_name[:-4] +\
                    '/meshes/{0}_{1:02d}'.format(meshes[i]["name"], j),\
                    node_list = node_list, complete_maps = complete_maps)
        if not os.path.exists(it3_name[:-4] + '/textures'):
            os.mkdir(it3_name[:-4] + '/textures')
        for i in range(len(textures)):
            with open(it3_name[:-4] + '/textures/{0}.dds'.format(textures[i]["name"]), 'wb') as f:
                f.write(textures[i]["texture"])
    return

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire mesh skeleton", action="store_true")
        parser.add_argument('-t', '--trim_for_gpu', help="Trim vertex buffer for GPU injection (3DMigoto)", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('it3_filename', help="Name of it3 file to export from (required).")
        args = parser.parse_args()
        if os.path.exists(args.it3_filename) and args.it3_filename[-4:].lower() == '.it3':
            process_it3(args.it3_filename, complete_maps = args.completemaps, trim_for_gpu = args.trim_for_gpu, overwrite = args.overwrite)
    else:
        it3_files = glob.glob('*.it3')
        for i in range(len(it3_files)):
            process_it3(it3_files[i])
