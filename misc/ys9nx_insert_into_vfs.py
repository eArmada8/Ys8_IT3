# Tool to replace files in the data.vfs archive in the Switch version of Ys IX: Monstrum Nox.
#
# This script requires the original data.vfs to be present in the folder with the script.
# Files to be replaced should be placed in a folder {name of .vfs file without .vfs}/path/to/file.
# For example, if you want to replace /chr/pc/c0000.it3 in data.vfs, then the file should be
# in data/chr/pc/. (This location is identical to the location that ys9nx_extract_vfs.py extracts
# the original to.)
#
# Only files in the data folder will be replaced, all other files will be untouched.  This script
# processes the files in the order they exist in the binary blob, to minimize changes to the blob
# itself.  New files are stored uncompressed and inserted in their original location.  This allows
# for the creation of very small patches when using a patching system such as Delta Patcher.  To
# significantly reduce processing time, the original files are not decompressed to check for
# changes - therefore all files that are present will be replaced.  (So even though
# ys9nx_extract_vfs.py will extract all 30K+ files, you only want to have *changed* files present
# in the data folder when running this script.)
#
# Thank you to MasaGratoR (github.com/masagrator/NXGameScripts), my understanding of the file format was
# derived from their scripts although the code is entirely written by me.
#
# For command line options, run:
# /path/to/python3 ys9nx_insert_into_vfs.py --help
#
# GitHub eArmada8/Ys8_IT3

try:
    import struct, zstandard, glob, os, sys
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def parse_vfs_file_with_folders (f):
    def read_str (f):
        len_, = struct.unpack("<I", f.read(4))
        return (f.read(len_).decode())
    def full_path (i, folders, dirnames):
        if folders[i]['parent_id'] < 0:
            return dirnames[folders[i]['folder_id']]
        else:
            parent_full_path = full_path(folders[i]['parent_id'], folders, dirnames)
            return (parent_full_path + '/' + dirnames[folders[i]['folder_id']])
    folders, files = [], []
    f.seek(0)
    magic = f.read(4)
    if magic == b'VFS3':
        header_size, version, num_folders = struct.unpack("<3I", f.read(12))
        for i in range(num_folders):
            folder_ = struct.unpack("<I6i", f.read(0x1c))
            folders.append({'crc': folder_[0], 'folder_id': folder_[1], 'parent_id': folder_[2], 'first_child': folder_[3],
                'num_children': folder_[4], 'unk0': folder_[5], 'num_files': folder_[6]})
        num_files, = struct.unpack("<I", f.read(4))
        for i in range(num_files):
            file_ = struct.unpack("<3QI3i", f.read(0x28))
            files.append({'offset': file_[0], 'cmp_size': file_[1], 'unc_size': file_[2], 'crc': file_[3],
            'file_id': file_[4], 'flags': file_[5], 'folder_id': file_[6]})
        chunk_table_offset, dictionary_offset = struct.unpack("<2Q", f.read(16))
        while f.tell() % 16 > 0:
            f.seek(1,1) # 16-bit alignment
        file_block_offset = f.tell()
        f.seek(chunk_table_offset)
        chunk_table_size, = struct.unpack("<I", f.read(4))
        chunk_tables = []
        while f.tell() < chunk_table_offset + chunk_table_size:
            table_size, = struct.unpack("<I", f.read(4))
            chunk_tables.append(list(struct.unpack("<{}i".format(table_size // 4), f.read(table_size))))
        f.seek(dictionary_offset)
        num_filenames, = struct.unpack("<I", f.read(4))
        filenames = [read_str(f) for _ in range(num_filenames)]
        num_dir_names, = struct.unpack("<I", f.read(4))
        dirnames = [read_str(f) for _ in range(num_dir_names)]
        for i in range(len(folders)):
            folders[i]['path'] = full_path (folders[i]['folder_id'], folders, dirnames)
        for i in range(len(files)):
            files[i]['filename'] = filenames[files[i]['file_id']]
            files[i]['location'] = folders[files[i]['folder_id']]['path']
            files[i]['chunk_table'] = chunk_tables[files[i]['file_id']]
            files[i]['true_offset'] = files[i]['offset'] + file_block_offset
    return (files, folders)

def round_up_align (val, align = 16):
    return ((val // align) * align + align if val % align > 0 else val)

# New files are inserted uncompressed
def compress_file (unc_data):
    block_sizes = [-0x20000]*(len(unc_data)//0x20000)+([len(unc_data)%0x20000 * -1] if len(unc_data)%0x20000 else [])
    return(unc_data, block_sizes)

# The file pointer f points to the original data.vfs
def build_data_block (f, all_files, base_folder):
    filedata_block = bytearray()
    # Files are processed in the order they are packed into the binary blob to minimize changes
    files_sorted_by_offset = []
    sorted_offsets = sorted(list(set([x['offset'] for x in all_files])))
    print("Rebuilding binary blob while replacing files, this takes some time...")
    for offset in sorted_offsets:
        files_at_offset = [x for x in all_files if x['offset'] == offset]
        non_dups = sorted(list(set([x['unc_size'] for x in files_at_offset])))
        # By definition, non_dups cannot have more than two entries, and only if the first is 0
        for i in range(len(non_dups)): 
            dups_at_offset = [x for x in files_at_offset if x['unc_size'] == non_dups[i]]
            # Search for files that need to be replaced (they will not be de-duplicated)
            to_skip, to_replace = [], []
            for file in dups_at_offset:
                if os.path.exists(base_folder + file['location'] + '/' + file['filename']):
                    to_replace.append(file)
                else:
                    to_skip.append(file)
            if len(to_skip) > 0:
                for file in to_skip:
                    all_files[file['i']]['offset'] = len(filedata_block)
                # If to_skip has more than one file, they are de-duplicated duplicates.  Copy data once only.
                f.seek(to_skip[0]['true_offset'])
                filedata_block.extend(f.read(to_skip[0]['cmp_size']))
                while len(filedata_block) % 16 > 0:
                    filedata_block.extend(b'\x00')
            if len(to_replace) > 0:
                for file in to_replace:
                    print("Replacing {}".format(file['location'] + '/' + file['filename']))
                    new_unc_data = open(base_folder + file['location'] + '/' + file['filename'], 'rb').read()
                    new_cmp_data, new_block_table = compress_file(new_unc_data)
                    all_files[file['i']]['offset'] = len(filedata_block)
                    all_files[file['i']]['cmp_size'] = len(new_cmp_data)
                    all_files[file['i']]['unc_size'] = len(new_unc_data)
                    all_files[file['i']]['chunk_table'] = new_block_table
                    filedata_block.extend(new_cmp_data)
                    while len(filedata_block) % 16 > 0:
                        filedata_block.extend(b'\x00')
    return (filedata_block, all_files)

# All file names and folders are preserved; new files are injected into the binary blob
def rebuild_vfs (vfs_filename):
    with open(vfs_filename + '.original', 'rb') as f:
        # Read original vfs file
        all_files, folders = parse_vfs_file_with_folders(f)
        base_folder = '.'.join(vfs_filename.split('.')[:-1])
        for i in range(len(all_files)):
            all_files[i]['i'] = i # Needed for writing back to the original all_files dictionary
        # Rebuild the giant binary blob and update all pointers in all_files
        filedata_block, all_files = build_data_block (f, all_files, base_folder)
        # Rebuilding zstandard frame blocks table
        print("Rebuilding file tables...")
        file_i_by_id = {x['file_id']:x['i'] for x in all_files}
        chunk_table_block = bytearray()
        for i in range(len(all_files)):
            chunk_table = all_files[file_i_by_id[i]]['chunk_table']
            chunk_table_block.extend(struct.pack("<I{}i".format(len(chunk_table)), len(chunk_table) * 4, *chunk_table))
        chunk_table_block = struct.pack("<I", len(chunk_table_block)) + chunk_table_block
        print("Rebuilding {}...".format(vfs_filename))
        header_block = bytearray(b'VFS3' + struct.pack("<2I", 0x10, 1))
        # Folders are inserted as-is without modification
        header_block.extend(struct.pack("<I", len(folders)))
        for i in range(len(folders)):
            header_block.extend(struct.pack("<I6i", *list(folders[i].values())[:7]))
        f.seek(len(header_block) + 4 + (0x28 * len(all_files)) + 8)
        dictionary_offset, = struct.unpack("<Q", f.read(8))
        f.seek(dictionary_offset)
        dictionary_block = f.read()
        header_block.extend(struct.pack("<I", len(all_files)))
        for i in range(len(all_files)):
            header_block.extend(struct.pack("<3QI3i", *list(all_files[i].values())[:7]))
        new_file_block_offset = round_up_align(len(header_block) + 16, 16)
        new_chunk_table_offset = new_file_block_offset + len(filedata_block)
        new_dictionary_offset = new_chunk_table_offset + len(chunk_table_block)
        header_block.extend(struct.pack("<2Q", new_chunk_table_offset, new_dictionary_offset))
        while len(header_block) % 16 > 0:
            header_block.extend(b'\x00')
        return(header_block + filedata_block + chunk_table_block + dictionary_block)

def rebuild_vfs_file (vfs_filename = 'data.vfs'):
    if os.path.exists(vfs_filename) and not os.path.exists(vfs_filename + '.original'):
        os.rename(vfs_filename, vfs_filename + '.original')
    new_vfs = rebuild_vfs (vfs_filename)
    open(vfs_filename,'wb').write(new_vfs)    
    return

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
        parser.add_argument('vfs_filename', help="Name of vfs file to rebuild (required).")
        args = parser.parse_args()
        vfs_filename = args.vfs_filename.split('.original')[0]
        if ((os.path.exists(vfs_filename) or os.path.exists(vfs_filename + '.original'))
                and vfs_filename[-4:].lower() == '.vfs'):
            rebuild_vfs_file(vfs_filename)
    else:
        vfs_files = sorted(list(set(glob.glob('*.vfs')
            + [x.split('.original')[0] for x in glob.glob('*.vfs.original')])))
        for i in range(len(vfs_files)):
            rebuild_vfs_file(vfs_files[i])