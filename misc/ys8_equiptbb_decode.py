# GitHub eArmada8/Ys8_IT3

try:
    import struct, re, io, csv, os, sys
    from lib_falcompress import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def read_string (data,offset):
    end = data.find(b'\x00',offset)
    if end == -1:
        return(data[offset:].decode())
    else:
        return(data[offset:end].decode())

#Reads defines, but with the number value being the key (for decoding)
def read_defines_rev (define_file):
    with open(define_file, 'rb') as f:
        try:
            def_data = f.read().decode('utf-8').replace('\r\n','\n').split('\n')
        except UnicodeDecodeError:
            f.seek(0,0)
            def_data = f.read().decode('cp932').replace('\r\n','\n').split('\n')
    defines = [x for x in [re.split(r'\t+', x)[1:3] for x in def_data if x[:7] == '#define'] if len(x) > 1 and x[1][0].isdigit()]
    return({int(x[1],16) if x[1][0:2].lower() == '0x' else int(x[1]):x[0] for x in defines})

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    mons_d = read_defines_rev('mons.h')
    icon_d = read_defines_rev('3dicon.h')
    with open('equip.tbb','rb') as f:
        f.seek(16)
        num_rows,strblocklen = struct.unpack("<2I",f.read(8))
        data_block = parse_data_blocks(f)
        rows = []
        row_types = {0:'BODY', 1:'ADDON', 3:'ACCESSORY', 4:'FGFIRE', 5:'UI_CAMP_FACE',\
            6:'UI_CAMP_BUST', 7:'UI_CAMP_SKILL', 8:'UI_BTL_FACE', 9:'UI_BTL_EFX'}
        block1 = data_block[:num_rows*0x10]
        block2 = data_block[num_rows*0x10:]
        with io.BytesIO(block1) as f:
            for i in range(num_rows):
                row_data = struct.unpack("<h2B3I", f.read(16))
                char = mons_d[row_data[1]] if row_data[1] in mons_d else row_data[1]
                item = icon_d[row_data[0]] if row_data[0] in icon_d else row_data[0]
                if row_data[2] != 4:
                    rows.append([row_types[row_data[2]],char,item,read_string(block2,row_data[4]),read_string(block2,row_data[5]),row_data[3]])
                else:
                    rows.append([row_types[row_data[2]],char,item,read_string(block2,row_data[4]),row_data[5],row_data[3]])
        with open('equip.csv','w', newline='') as f:
            csvw = csv.writer(f)
            for i in range(len(rows)):
                csvw.writerow(rows[i])