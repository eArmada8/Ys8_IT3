# Library implementation of Falcom's Mode 3 (C77) and Mode 2 (BZ) algorithms.
# Thank you to Twnkey, uyjulian and Kyuuhachi (Aureole-Suite)!
# Usage:  Decompress with parse_data_blocks (f), compress with create_data_blocks (content, mode)
#
# GitHub eArmada8/Ys8_IT3

import struct, io, array

# C77 aka FALCOM3, thank you to TwnKey
def parse_data_block_new (f, block_size, uncompressed_block_size, is_compressed):
    if is_compressed:
        contents = bytearray(uncompressed_block_size)
        start = f.tell()
        i = 0
        while f.tell() < start + block_size - 4:
            current_byte1, current_byte2 = struct.unpack("<2B", f.read(2))
            if (current_byte1 == 0):
                contents[i:i+current_byte2] = f.read(current_byte2)
                i = i + current_byte2
            else:
                for _ in range(current_byte1):
                    contents[i] = contents[i-1-current_byte2]
                    i = i + 1
                contents[i:i+1] = f.read(1)
                i = i + 1
    else:
        contents = f.read(block_size - 4)
    return(contents)

# Thank you to uyjulian, source: https://gist.github.com/uyjulian/a6ba33dc29858327ffa0db57f447abe5
# Reference: CEgPacks2::UnpackBZMode2
# Also known as falcom_compress / BZ / BZip / zero method aka FALCOM2
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

# Accepts a byte stream (e.g. open file handle or BytesIO object)
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
            data += parse_data_block_new(f, block_size, uncompressed_block_size, is_compressed)
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

# My best attempt at recreating the Ys VIII compression algorithm (C77 aka FALCOM3).
# Content should be a bytes-like object.
def compress_data_block(content):
    #print("Compressing data block.")
    result = bytes()
    offset = 0 # First byte of search buffer, anything behind this is already copied to result
    window = 1 # First byte of look-ahead buffer
    if len(content) > 2:
        while window < len(content):
            if content.find(content[window], offset, window) != -1:
                byte_matches = [x for x in range(offset, window) if content[x] == content[window]]
                for i in range(len(byte_matches)):
                    if content[byte_matches[i]:window] == content[window:(window*2-byte_matches[i])]:
                        len_repeat = window - byte_matches[i]
                        num_repeats = 1
                        while content[byte_matches[i]:window] ==\
                            content[window + (num_repeats * len_repeat):(window*2-byte_matches[i]) + (num_repeats * len_repeat)]:
                            num_repeats += 1
                        num_repeats = min(num_repeats, 255 // len_repeat)
                        if window + len_repeat * num_repeats >= len(content):
                            num_repeats -= 1 # Compressed sequence cannot end on a repeat
                        if len_repeat * num_repeats > 1: # Do not compress doublet bytes, which increase file size
                            result += struct.pack("<2B", 0, (window-offset)) + content[offset:window] +\
                                struct.pack("<2B", len_repeat * num_repeats, len_repeat - 1)
                            offset = window + len_repeat * num_repeats
                            window = offset + 1 
                            result += content[offset:window]
                            offset += 1
                            break
            if window - offset >= 255: # In actuality, window == 255 is fine
                result += struct.pack("<2B", 0, 255) + content[offset:window]
                offset = window
            #if (window % (len(content) // 5) == 0):
                #print("Progress: {0}%".format(round(window * 10 // (len(content)))*10))
            window += 1
        if offset < len(content):
            result += struct.pack("<2B", 0, (window-offset)) + content[offset:window]
    else:
        result = content
    return(result)

# Source: github.com/Aureole-Suite/Falcompress, thank you to Kyuuhachi
def compress_mode2(input_):
    def count_equal (a, b, limit = 4096):
        aa = a[:limit]
        bb = b[:limit]
        if aa == bb:
            return(len(aa))
        count = 0
        for count in range(min(len(aa),len((bb)))):
            if aa[count] != bb[count]:
                break
        return count
    class Digraphs:
        def __init__(self, input_):
            self.input_ = input_ # The data to be compressed
            self.pos = 0
            self.head = array.array('H', [0xFFFF]*0x10000)
            self.next_ = array.array('H', [0xFFFF]*0x2000)
            self.tail = array.array('H', [0xFFFF]*0x10000)
        def digraph(self, pos):
            if pos < len(self.input_):
                if pos + 1 < len(self.input_):
                    value, = struct.unpack('<H', self.input_[pos:pos+2])
                else:
                    value = self.input_[pos] # Returns an int
                return (value)
            else:
                return False
        def advance(self):
            if self.pos >= 0x1FFF:
                prev_pos = self.pos - 0x1FFF
                dig = self.digraph(prev_pos)
                self.head[dig] = self.next_[prev_pos % len(self.next_)]
            dig = self.digraph(self.pos)
            if self.head[dig] == 0xFFFF:
                self.head[dig] = self.pos & 0xFFFF
            else:
                self.next_[self.tail[dig]] = self.pos & 0xFFFF
            self.tail[dig] = (self.pos % len(self.next_)) & 0xFFFF
            self.next_[self.pos % len(self.next_)] = 0xFFFF
            self.pos += 1
            return
        def get(self, rep_len, rep_pos):
            pos = self.head[self.digraph(self.pos)]
            while pos != 0xFFFF:
                len_ = count_equal(self.input_[self.pos+2:], self.input_[pos+2:], 267) + 2
                if len_ >= rep_len:
                    rep_len, rep_pos = len_, pos
                pos = self.next_[pos % len(self.next_)]
            return(rep_len, rep_pos)
    class Bits:
        def __init__(self, out):
            self.out = array.array('B',out)
            self.bit_mask = 0x0080
            self.bitpos = len(self.out)
            self.out.extend([0,0])
        def bit(self, v): #v is boolean
            self.bit_mask <<= 1
            self.bit_mask = self.bit_mask & 0xFFFF # Bit mask is u16, this enforces left shift with bit loss
            if self.bit_mask == 0:
                self.bitpos = len(self.out)
                self.out.extend([0,0])
                self.bit_mask = 0x0001
            if v:
                if self.bit_mask < 0x0100:
                    self.out[self.bitpos] |= self.bit_mask & 0xFF
                else:
                    self.out[self.bitpos+1] |= (self.bit_mask >> 8) & 0xFF
            return(v) #
        def bits(self, n, v): #n and v are integers
            assert (v < (1 << n)) #raises an AssertionError
            for k in range(n - 1, n // 8 * 8 - 1, -1):
                self.bit((v >> k) & 1 != 0)
            for k in range(n // 8 - 1, -1, -1):
                self.out.append((v >> (k * 8)) & 0xFF)
            return
        def byte(self, v):
            self.out.append(v)
            return
    # Code start
    assert(len(input_) < 0xFFFF)
    input_pos = 0
    b = Bits(b'')
    dig = Digraphs(input_)
    while input_pos < len(input_):
        run_len = count_equal(input_[input_pos:], input_[input_pos+1:], 0xFFE) + 1
        if run_len < 14:
            run_len = 1
        run_pos = input_pos
        if (run_len < 64) and (input_pos + 3 < len(input_)):
            run_len, run_pos = dig.get(run_len, run_pos)
        assert(run_len > 0)
        if b.bit(run_len > 1):
            if run_pos == input_pos:
                b.bit(True)
                b.bits(13,1)
                n = run_len - 14
                if b.bit(n >= 16):
                    b.bits(12, n)
                else:
                    b.bits(4, n)
                b.byte(input_[input_pos])
            else:
                n = input_pos - run_pos
                if b.bit(n >= 256):
                    b.bits(13, n)
                else:
                    b.bits(8, n)
                m = run_len
                if m >= 3:
                    b.bit(False)
                if m >= 4:
                    b.bit(False)
                if m >= 5:
                    b.bit(False)
                if m >= 6:
                    b.bit(False)
                if b.bit(m < 14):
                    if m >= 6:
                        b.bits(3, m - 6)
                else:
                    b.bits(8, m - 14)
        else:
            b.byte(input_[input_pos])
        for _ in range(run_len):
            input_pos += 1
            dig.advance()
    b.bit(True)
    b.bit(True)
    b.bits(13,0)
    return(b.out.tobytes())

def compress_data_mode2(data):
    def chunk_bytes(data, chunk_size):
        if len(data) > 0:
            return([data[i*chunk_size : (i+1)*chunk_size] for i in range((len(data) - 1) // chunk_size + 1)])
        else:
            return([])
    def compressed_chunk(chunk_data):
        cchunk = compress_mode2(chunk_data)
        return(struct.pack("<H", len(cchunk) + 2) + cchunk)
    chunk_data = chunk_bytes(data, 0x7FF0)
    cdata = bytes()
    for i in range(len(chunk_data)):
        print("Compressing data chunk {0} of {1}.".format(i+1, len(chunk_data)))
        cdata += compressed_chunk(chunk_data[i]) + b'\x01'
    cdata += compressed_chunk(chunk_data[-1][0].to_bytes()) if len(chunk_data) > 0 else compressed_chunk(b'') + b'\x00'
    return(struct.pack("<3I", len(cdata) + 8, len(data), len(chunk_data) + 1) + cdata)

# Content should be a bytes-like object.
def create_data_blocks (content, mode = 3):
    if mode == 3:
        segment_size = 0x40000 # Separate into chunks of this size prior to compression
        uncompressed_sizes = [len(content[i:i+segment_size]) for i in range(0, max(1,len(content)), segment_size)]
        print("Compressing {0} data blocks...".format(len(uncompressed_sizes)))
        compressed_content = [compress_data_block(content[i:i+segment_size]) for i in range(0, max(1,len(content)), segment_size)]
        compressed_sizes = [len(x) for x in compressed_content]
        compressed_block = struct.pack("<5I", 0x80000001, len(uncompressed_sizes), sum([x+12 for x in compressed_sizes]),\
            max([x+12 for x in compressed_sizes]), len(content)) +\
            b''.join([(struct.pack("<3I", compressed_sizes[i]+4, uncompressed_sizes[i], 8) + compressed_content[i]) for i in range(len(uncompressed_sizes))])
        return(compressed_block)
    elif mode == 2:
        return(compress_data_mode2(content))
    else:
        print("Only C77 (mode 3) and mode 2 variant of bz currently supported.")
        raise