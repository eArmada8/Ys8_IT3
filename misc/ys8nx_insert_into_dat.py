# Tool to replace files in the data.dat archive in the Switch version of Ys VIII: Lacrimosa of Dana.
#
# This script requires the original data.dat to be present in the folder with the script.
# Files to be replaced should be placed in a folder {name of .dat file without .dat}/path/to/file.
# For example, if you want to replace /chr/pc/c000.it3 in data.dat, then the file should be
# in data/chr/pc/. (This location is identical to the location that ys8nx_extract_dat.py extracts
# the original to.)
#
# Only files in the data folder will be replaced, all other files will be untouched.  This script
# processes the files in the order they exist in the binary blob, to minimize changes to the blob
# itself.  New files are stored uncompressed and inserted in their original location.  This allows
# for the creation of very small patches when using a patching system such as Delta Patcher.  To
# significantly reduce processing time, the original files are not read from data.dat to check for
# changes - therefore all files that are present will be replaced.  (So even though
# ys8nx_extract_dat.py will extract all 28+ files, you only want to have *changed* files present
# in the data folder when running this script.)
#
# Thank you to Luigi Auriemma (https://aluigi.altervista.org/quickbms.htm), my understanding of the file
# format was derived from their scripts although the code is entirely written by me.
#
# For command line options, run:
# /path/to/python3 ys8nx_insert_into_dat.py --help
#
# GitHub eArmada8/Ys8_IT3

try:
    import struct, glob, os, sys
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

# Read a null-terminated string
def read_string (f):
    raw = bytearray(f.read(1))
    while not raw[-1] == 0:
        raw.extend(f.read(1))
    string = raw[:-1].decode('ansi')
    return string

def parse_dat_file_with_header (f):
    f.seek(0)
    magic = f.read(8)
    if magic == b'FAFULLFS':
        header = {}
        header['num_files'], header['names_offset'], header['names_size'], header['info_offset'] = struct.unpack(
            "<4Q", f.read(32))
        files = []
        f.seek(header['info_offset'])
        for i in range(header['num_files']):
            file = {}
            file['hash'], file['name_offset'], file['unk0'], file['size'], file['offset'], file['datetime'] = struct.unpack(
            "<6Q", f.read(48))
            files.append(file)
        for i in range(header['num_files']):
            f.seek(files[i]['name_offset'] + header['names_offset'])
            files[i]['full_filepath'] = read_string (f)
            files[i]['filepath'] = os.path.dirname(files[i]['full_filepath'])
            files[i]['filename'] = os.path.basename(files[i]['full_filepath'])
    return files, header

# The file pointer f points to the original data.dat
def build_data_block (f, all_files, base_folder):
    filedata_block = bytearray()
    # Preserve original offsets
    for i in range(len(all_files)):
        all_files[i]['original_offset'] = all_files[i]['offset']
    # Files are processed in the order they are packed into the binary blob to minimize changes
    files_sorted_by_offset = []
    sorted_offsets = sorted(list(set([x['original_offset'] for x in all_files])))
    print("Rebuilding binary blob while replacing files, this takes some time...")
    for offset in sorted_offsets:
        files_at_offset = [x for x in all_files if x['original_offset'] == offset]
        non_dups = sorted(list(set([x['size'] for x in files_at_offset])))
        # By definition, non_dups cannot have more than two entries, and only if the first is 0
        for i in range(len(non_dups)): 
            dups_at_offset = [x for x in files_at_offset if x['size'] == non_dups[i]]
            # Search for files that need to be replaced (they will not be de-duplicated)
            to_skip, to_replace = [], []
            for file in dups_at_offset:
                if os.path.exists(base_folder + '/' + file['full_filepath']):
                    to_replace.append(file)
                else:
                    to_skip.append(file)
            if len(to_skip) > 0:
                for file in to_skip:
                    all_files[file['i']]['offset'] = len(filedata_block) + 512
                    f.seek(file['original_offset'])
                    filedata_block.extend(f.read(file['size']))
                    while len(filedata_block) % 512 > 0:
                        filedata_block.extend(b'\x00')
            if len(to_replace) > 0:
                for file in to_replace:
                    print("Replacing {}".format(file['full_filepath']))
                    new_file_data = open(base_folder + '/' + file['full_filepath'], 'rb').read()
                    all_files[file['i']]['offset'] = len(filedata_block) + 512
                    all_files[file['i']]['size'] = len(new_file_data)
                    filedata_block.extend(new_file_data)
                    while len(filedata_block) % 512 > 0:
                        filedata_block.extend(b'\x00')
    return (filedata_block, all_files)

# All file names and folders are preserved; new files are injected into the binary blob
def rebuild_dat (dat_filename):
    with open(dat_filename + '.original', 'rb') as f:
        # Read original dat file
        all_files, header = parse_dat_file_with_header(f)
        base_folder = '.'.join(dat_filename.split('.')[:-1])
        for i in range(len(all_files)):
            all_files[i]['i'] = i # Needed for writing back to the original all_files dictionary
        # Rebuild the giant binary blob and update all pointers in all_files
        filedata_block, all_files = build_data_block (f, all_files, base_folder)
        # Rebuild the file info block and file name block at the end of the .dat file
        print("Rebuilding file tables...")
        fileinfo_block = bytearray()
        for i in range(len(all_files)):
            fileinfo_block.extend(struct.pack("<6Q", *list(all_files[i].values())[:6]))
        fileinfo_block_len = len(fileinfo_block)
        # Append the filenames as-is (we cannot add / delete files or change file names without the hashing code)
        f.seek(header['names_offset'])
        fileinfo_block.extend(f.read())
        print("Rebuilding {}...".format(dat_filename))
        header_block = bytearray(b'FAFULLFS')
        header_block.extend(struct.pack("<4Q", len(all_files),
            512 + len(filedata_block) + fileinfo_block_len,
            len(fileinfo_block) - fileinfo_block_len,
            512 + len(filedata_block)))
        while len(header_block) % 512 > 0:
            header_block.extend(b'\x00')
        return(header_block + filedata_block + fileinfo_block)

def rebuild_dat_file (dat_filename = 'data.dat'):
    if os.path.exists(dat_filename) and not os.path.exists(dat_filename + '.original'):
        os.rename(dat_filename, dat_filename + '.original')
    new_dat = rebuild_dat(dat_filename)
    open(dat_filename,'wb').write(new_dat)    
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
        parser.add_argument('dat_filename', help="Name of dat file to rebuild (required).")
        args = parser.parse_args()
        dat_filename = args.dat_filename.split('.original')[0]
        if ((os.path.exists(dat_filename) or os.path.exists(dat_filename + '.original'))
                and dat_filename[-4:].lower() == '.dat'):
            rebuild_dat_file(dat_filename)
    else:
        dat_files = sorted(list(set(glob.glob('*.dat')
            + [x.split('.original')[0] for x in glob.glob('*.dat.original')])))
        for i in range(len(dat_files)):
            rebuild_dat_file(dat_files[i])