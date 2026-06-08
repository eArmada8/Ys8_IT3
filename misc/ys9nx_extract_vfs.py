# Tool to extract files from the data.vfs archive in the Switch version of Ys IX: Monstrum Nox.
#
# By default, it will extract all files from data.vfs into the folder `data` (or any file filename.vfs
# into a corresponding folder `filename`).  Using the command line, a list of files can be passed to
# the script to extract only those files (end the list with --, then specify the vfs file).  For example,
# invoking the script as such:
# > python3 ys9nx_extract_vfs.py --files c0010.it3 c0011.it3 -- data.vfs
# will extract only c0010.it3 c0011.it3 files from data.vfs.
#
# Thank you to MasaGratoR (github.com/masagrator/NXGameScripts), my understanding of the file format was
# derived from their scripts although the code is entirely written by me.
#
# For command line options, run:
# /path/to/python3 ys9nx_extract_vfs.py --help
#
# GitHub eArmada8/Ys8_IT3

try:
    import struct, zstandard, glob, os, sys
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def read_file (f, file_entry):
    decomp = zstandard.ZstdDecompressor()
    f.seek(file_entry['true_offset'])
    if file_entry['flags'] & 0x3: # Compressed
        cmp_data = bytearray(b'\x28\xB5\x2F\xFD\x00\x88')
        for i in range(len(file_entry['chunk_table'])):
            chunk = f.read(abs(file_entry['chunk_table'][i]))
            cmp_data.extend(((len(chunk)<<3)
                + (4 if file_entry['chunk_table'][i]>=0 else 0)).to_bytes(3,byteorder='little'))
            cmp_data.extend(chunk)
        cmp_data.extend(b'\x01\x00\x00')
        unc_data = decomp.decompress(cmp_data, max_output_size = file_entry['unc_size'])
    else:
        unc_data = f.read(file_entry['unc_size'])
    return (unc_data)

def parse_vfs_file (f):
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
    return (files)

# Function to extract files.  If files_to_extract is an empty list, all files will be extracted.
def extract_files (vfs_filename, files_to_extract = [], overwrite = False):
    with open(vfs_filename,'rb') as f:
        all_files = parse_vfs_file(f)
        if len(files_to_extract) > 0:
            files = [x for x in all_files if x['filename'] in files_to_extract]
        else:
            files = all_files
        base_folder = '.'.join(vfs_filename.split('.')[:-1])
        if os.path.exists(base_folder) and (os.path.isdir(base_folder)) and (overwrite == False):
            if str(input(base_folder + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(base_folder):
            all_folders = sorted(list(set([x['location'] for x in files])))
            for i in range(len(all_folders)):
                if not os.path.exists(base_folder + all_folders[i]):
                    os.makedirs(base_folder + all_folders[i])
            for i in range(len(files)):
                print("Extracting {}".format(files[i]['location'] + '/' + files[i]['filename']))
                file_data = read_file (f, files[i])
                open(base_folder + files[i]['location'] + '/' + files[i]['filename'], 'wb').write(file_data)
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
        parser.add_argument('-f', '--files', nargs='*', default=[], help="Specify which files to extract (end list with --).")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('vfs_filename', help="Name of vfs file to extract from (required).")
        args = parser.parse_args()
        if os.path.exists(args.vfs_filename) and args.vfs_filename[-4:].lower() == '.vfs':
            extract_files(args.vfs_filename, files_to_extract = args.files, overwrite = args.overwrite)
    else:
        vfs_files = glob.glob('*.vfs')
        for i in range(len(vfs_files)):
            extract_files(vfs_files[i])