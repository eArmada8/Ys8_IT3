# GitHub eArmada8/Ys8_IT3

try:
    import struct, re, csv, os, sys, shutil
    from lib_falcompress import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

#Reads defines, with the name value being the key (for encoding)
def read_defines (define_file):
    with open(define_file, 'rb') as f:
        try:
            def_data = f.read().decode('utf-8').replace('\r\n','\n').split('\n')
        except UnicodeDecodeError:
            f.seek(0,0)
            def_data = f.read().decode('cp932').replace('\r\n','\n').split('\n')
    defines = [x for x in [re.split(r'\t+', x)[1:3] for x in def_data if x[:7] == '#define'] if len(x) > 1 and x[1][0].isdigit()]
    return({x[0]:int(x[1],16) if x[1][0:2].lower() == '0x' else int(x[1]) for x in defines})

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    mons_d = read_defines('mons.h')
    icon_d = read_defines('3dicon.h')
    if os.path.exists('equip.csv'):
        with open('equip.csv', newline='') as f:
            csvr = list(csv.reader(f))
            block1 = bytes()
            block2 = b'\x00'
            row_types = {'BODY':0, 'ADDON':1, 'ACCESSORY':3, 'FGFIRE':4, 'UI_CAMP_FACE':5,\
                'UI_CAMP_BUST':6, 'UI_CAMP_SKILL':7, 'UI_BTL_FACE':8, 'UI_BTL_EFX':9}
            for i in range(len(csvr)):
                if csvr[i][0] in row_types:
                    row_type = row_types[csvr[i][0]]
                else:
                    print("Row Type on row {} is invalid!".format(i))
                    raise
                if csvr[i][1].isdigit():
                    char = int(csvr[i][1])
                elif csvr[i][1] in mons_d:
                    char = mons_d[csvr[i][1]]
                else:
                    print("Character on row {} is invalid!".format(i))
                    raise
                if csvr[i][2].lstrip('-').isdigit():
                    item = int(csvr[i][2])
                elif csvr[i][2] in icon_d:
                    item = icon_d[csvr[i][2]]
                else:
                    print("Item on row {} is invalid!".format(i))
                    raise
                if row_type in [1,3,4]: # Node
                    node_loc = len(block2)
                    block2 += csvr[i][3].encode('cp932') + b'\x00'
                else:
                    node_loc = 0
                if row_type in [0,1,3,5,6,7,8,9]: # Path
                    path_loc = len(block2)
                    block2 += csvr[i][4].encode('cp932') + b'\x00'
                else:
                    path_loc = int(csvr[i][4]) #FGFIRE, storing fireno in path_loc
                block1 += struct.pack("<h2B3I", item, char, row_type, int(csvr[i][5]), node_loc, path_loc)
        tbb = struct.pack("<6I", 1162955860, 65536, 2374712759, 197257069, len(csvr), len(block2)) \
            + create_data_blocks(block1+block2)
        # Instead of overwriting backups, it will just tag a number onto the end
        backup_suffix = ''
        if os.path.exists('equip.tbb.bak' + backup_suffix):
            backup_suffix = '1'
            if os.path.exists('equip.tbb.bak' + backup_suffix):
                while os.path.exists('equip.tbb.bak' + backup_suffix):
                    backup_suffix = str(int(backup_suffix) + 1)
            shutil.copy2('equip.tbb', 'equip.tbb.bak' + backup_suffix)
        else:
            shutil.copy2('equip.tbb', 'equip.tbb.bak')
        with open('equip.tbb','wb') as f:
            f.write(tbb)