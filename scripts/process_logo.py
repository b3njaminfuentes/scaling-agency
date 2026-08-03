import struct
import zlib
import os
import subprocess

def read_png(filename):
    with open(filename, 'rb') as f:
        data = f.read()
    
    pos = 8
    width = height = None
    idat_chunks = []
    while pos < len(data):
        length, chunk_type = struct.unpack('>I4s', data[pos:pos+8])
        pos += 8
        chunk_data = data[pos:pos+length]
        pos += length
        pos += 4 # crc
        
        if chunk_type == b'IHDR':
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack('>IIBBBBB', chunk_data)
        elif chunk_type == b'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == b'IEND':
            break
            
    decompressed = zlib.decompress(b''.join(idat_chunks))
    
    bytes_per_pixel = 4 if color_type == 6 else (3 if color_type == 2 else 1)
    stride = width * bytes_per_pixel
    pixels = bytearray(width * height * 4)
    
    raw_pos = 0
    prev_row = bytearray(stride)
    curr_row = bytearray(stride)
    
    for y in range(height):
        filter_type = decompressed[raw_pos]
        raw_pos += 1
        scanline = decompressed[raw_pos:raw_pos+stride]
        raw_pos += stride
        
        for x in range(stride):
            filt_byte = scanline[x]
            a = curr_row[x - bytes_per_pixel] if x >= bytes_per_pixel else 0
            b = prev_row[x]
            c = prev_row[x - bytes_per_pixel] if x >= bytes_per_pixel else 0
            
            if filter_type == 0: val = filt_byte
            elif filter_type == 1: val = (filt_byte + a) & 0xff
            elif filter_type == 2: val = (filt_byte + b) & 0xff
            elif filter_type == 3: val = (filt_byte + ((a + b) // 2)) & 0xff
            elif filter_type == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                val = (filt_byte + pr) & 0xff
            else: val = filt_byte
            curr_row[x] = val
            
        for x in range(width):
            out_idx = (y * width + x) * 4
            in_idx = x * bytes_per_pixel
            if bytes_per_pixel == 4:
                r, g, b, alpha = curr_row[in_idx:in_idx+4]
            elif bytes_per_pixel == 3:
                r, g, b = curr_row[in_idx:in_idx+3]
                alpha = 255
            pixels[out_idx:out_idx+4] = bytes([r, g, b, alpha])
            
        prev_row = bytearray(curr_row)
        
    return width, height, pixels

def write_png(filename, width, height, pixels):
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)
        start = y * width * 4
        raw_data.extend(pixels[start:start + width * 4])
        
    compressed = zlib.compress(bytes(raw_data), 9)
    out = bytearray(b'\x89PNG\r\n\x1a\n')
    
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    out.extend(struct.pack('>I4s', len(ihdr_data), b'IHDR'))
    out.extend(ihdr_data)
    out.extend(struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff))
    
    out.extend(struct.pack('>I4s', len(compressed), b'IDAT'))
    out.extend(compressed)
    out.extend(struct.pack('>I', zlib.crc32(b'IDAT' + compressed) & 0xffffffff))
    
    out.extend(struct.pack('>I4s', 0, b'IEND'))
    out.extend(struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff))
    
    with open(filename, 'wb') as f:
        f.write(out)

def process():
    w, h, px = read_png('assets/logo-raw.png')
    
    min_x, max_x = w, 0
    min_y, max_y = h, 0
    
    # First pass: find true arrow bounding box where pixel is clearly dark (< 180)
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = px[idx:idx+4]
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            if brightness < 180 and a > 50:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
                
    print(f"True Arrow BBox: x=[{min_x}, {max_x}] (w={max_x-min_x+1}), y=[{min_y}, {max_y}] (h={max_y-min_y+1})")
    
    pad = 12
    crop_min_x = max(0, min_x - pad)
    crop_max_x = min(w - 1, max_x + pad)
    crop_min_y = max(0, min_y - pad)
    crop_max_y = min(h - 1, max_y + pad)
    
    crop_w = crop_max_x - crop_min_x + 1
    crop_h = crop_max_y - crop_min_y + 1
    
    cropped_px = bytearray(crop_w * crop_h * 4)
    gold_px = bytearray(crop_w * crop_h * 4)
    white_px = bytearray(crop_w * crop_h * 4)
    
    for cy in range(crop_h):
        for cx in range(crop_w):
            orig_x = crop_min_x + cx
            orig_y = crop_min_y + cy
            src_idx = (orig_y * w + orig_x) * 4
            dst_idx = (cy * crop_w + cx) * 4
            
            r, g, b, a = px[src_idx:src_idx+4]
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            
            if brightness >= 240:
                alpha = 0
            elif brightness <= 50:
                alpha = 255
            else:
                alpha = int(255 * (1.0 - (brightness - 50) / 190.0))
                
            cropped_px[dst_idx:dst_idx+4] = bytes([18, 21, 28, alpha])
            gold_px[dst_idx:dst_idx+4] = bytes([164, 124, 59, alpha])
            white_px[dst_idx:dst_idx+4] = bytes([255, 255, 255, alpha])
            
    write_png('assets/logo.png', crop_w, crop_h, cropped_px)
    write_png('assets/logo-gold.png', crop_w, crop_h, gold_px)
    write_png('assets/logo-white.png', crop_w, crop_h, white_px)
    
    # Create square favicon with nice margin
    sq_dim = max(crop_w, crop_h) + 40
    sq_px = bytearray(sq_dim * sq_dim * 4)
    sq_gold = bytearray(sq_dim * sq_dim * 4)
    
    off_x = (sq_dim - crop_w) // 2
    off_y = (sq_dim - crop_h) // 2
    
    for cy in range(crop_h):
        for cx in range(crop_w):
            src_idx = (cy * crop_w + cx) * 4
            dst_idx = ((cy + off_y) * sq_dim + (cx + off_x)) * 4
            sq_px[dst_idx:dst_idx+4] = cropped_px[src_idx:src_idx+4]
            sq_gold[dst_idx:dst_idx+4] = gold_px[src_idx:src_idx+4]
            
    write_png('assets/favicon.png', sq_dim, sq_dim, sq_px)
    write_png('favicon.png', sq_dim, sq_dim, sq_px)
    write_png('assets/favicon-gold.png', sq_dim, sq_dim, sq_gold)
    write_png('apple-touch-icon.png', sq_dim, sq_dim, sq_px)
    
    # Generate favicon.svg with the exact curve path representation
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none">
  <!-- LIGHT PARTNERS ICON -->
  <path d="M42 27 L48 24 L52 29 L48 33 L45 31 C46 44 48 60 62 76 C60 77 56 75 53 71 C40 55 38 41 38 31 L35 33 L31 29 L35 24 Z" fill="#12151c"/>
  <path d="M48 24 L52 29 L48 33 L44 30 C45 45 47 62 63 77 C59 76 56 74 52 70 C39 54 38 39 38 30 L34 33 L30 29 L40 24 Z" fill="#a47c3b"/>
</svg>'''
    with open('favicon.svg', 'w') as f:
        f.write(svg_content)
    with open('assets/favicon.svg', 'w') as f:
        f.write(svg_content)
        
    print(f"Generated logo.png ({crop_w}x{crop_h}) and square favicon ({sq_dim}x{sq_dim})")

if __name__ == '__main__':
    process()
