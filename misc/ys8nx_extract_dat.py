# Tool to extract files from the data.dat archive in the Switch version of Ys VIII: Lacrimosa of Dana.
#
# By default, it will extract all files from data.dat into the folder `data` (or any file filename.dat
# into a corresponding folder `filename`).  Using the command line, a list of files can be passed to
# the script to extract only those files (end the list with --, then specify the dat file).  For example,
# invoking the script as such:
# > python3 ys8nx_extract_dat.py --files c000.it3 c001.it3 -- data.dat
# will extract only c000.it3 c001.it3 files from data.dat.
#
# Thank you to Luigi Auriemma (https://aluigi.altervista.org/quickbms.htm), my understanding of the file
# format was derived from their scripts although the code is entirely written by me.
#
# For command line options, run:
# /path/to/python3 ys8nx_extract_dat.py --help
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

def parse_dat_file (f):
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
    return files

# Function to extract files.  If files_to_extract is an empty list, all files will be extracted.
def extract_files (dat_filename, files_to_extract = [], overwrite = False):
    with open(dat_filename,'rb') as f:
        all_files = parse_dat_file(f)
        if len(files_to_extract) > 0:
            files = [x for x in all_files if x['filename'] in files_to_extract]
        else:
            files = all_files
        base_folder = '.'.join(dat_filename.split('.')[:-1])
        if os.path.exists(base_folder) and (os.path.isdir(base_folder)) and (overwrite == False):
            if str(input(base_folder + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(base_folder):
            all_folders = sorted(list(set([x['filepath'] for x in files])))
            for i in range(len(all_folders)):
                if not os.path.exists(base_folder + '/' + all_folders[i]):
                    os.makedirs(base_folder + '/' + all_folders[i])
            for i in range(len(files)):
                print("Extracting {}".format(files[i]['full_filepath']))
                f.seek(files[i]['offset'])
                file_data = f.read(files[i]['size'])
                #file_time = datetime.datetime.fromtimestamp(files[i]['datetime'])
                open(base_folder + '/' + files[i]['filepath'] + '/' + files[i]['filename'], 'wb').write(file_data)
                os.utime(base_folder + '/' + files[i]['filepath'] + '/' + files[i]['filename'],
                    (files[i]['datetime'], files[i]['datetime']))
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
        parser.add_argument('dat_filename', help="Name of dat file to extract from (required).")
        args = parser.parse_args()
        if os.path.exists(args.dat_filename) and args.dat_filename[-4:].lower() == '.dat':
            extract_files(args.dat_filename, files_to_extract = args.files, overwrite = args.overwrite)
    else:
        dat_files = glob.glob('*.dat')
        for i in range(len(dat_files)):
            extract_files(dat_files[i])