import zlib
import struct
import math
import os

def create_png(width, height, get_pixel_fn):
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0) # Filter byte 0 (None)
        for x in range(width):
            r, g, b, a = get_pixel_fn(x, y, width, height)
            raw_data.extend([int(r), int(g), int(b), int(a)])
    
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        crc = zlib.crc32(tag + data) & 0xffffffff
        return c + struct.pack(">I", crc)
    
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw_data), level=9)
    
    return header + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")

def make_favicon_pixel(x, y, w, h):
    # Normalized coordinates from -1 to 1
    # Supersampling 4x4
    samples = [
        (0.2, 0.2), (0.2, 0.8), (0.8, 0.2), (0.8, 0.8)
    ]
    
    # Colors
    bg_r, bg_g, bg_b = 18, 21, 28 # #12151c
    gold_r, gold_g, gold_b = 201, 169, 104 # #c9a968
    
    tot_r, tot_g, tot_b, tot_a = 0, 0, 0, 0
    radius = w * 0.22 # corner radius
    
    for sx, sy in samples:
        px = x + sx
        py = y + sy
        
        # Check rounded rect
        # Center is w/2, h/2
        dx = abs(px - w/2) - (w/2 - radius)
        dy = abs(py - h/2) - (h/2 - radius)
        
        in_bg = True
        if dx > 0 and dy > 0:
            if math.sqrt(dx*dx + dy*dy) > radius:
                in_bg = False
        elif dx > radius or dy > radius:
            in_bg = False
            
        if not in_bg:
            # transparent outside rounded rect
            continue
            
        # Inside bg: check sparkle shape
        # Center is w/2, h/2
        # Destello is defined by curve: |nx|^0.4 + |ny|^0.4 <= scale
        nx = (px - w/2) / (w * 0.40)
        ny = (py - h/2) / (h * 0.40)
        
        anx = abs(nx)
        any_ = abs(ny)
        
        in_sparkle = False
        if anx < 1.0 and any_ < 1.0:
            # 4-pointed star curve equation: (|x|)^0.45 + (|y|)^0.45 <= 1.0
            if (anx**0.55 + any_**0.55) <= 1.0:
                in_sparkle = True
                
        if in_sparkle:
            tot_r += gold_r
            tot_g += gold_g
            tot_b += gold_b
            tot_a += 255
        else:
            tot_r += bg_r
            tot_g += bg_g
            tot_b += bg_b
            tot_a += 255
            
    num_samples = len(samples)
    return (tot_r / num_samples, tot_g / num_samples, tot_b / num_samples, tot_a / num_samples)

def main():
    base_dir = "/Users/benjaminfuentes/.gemini/antigravity/scratch/scaling-agency"
    
    sizes = {
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "favicon.png": 64,
        "apple-touch-icon.png": 180,
        "android-chrome-192x192.png": 192,
        "android-chrome-512x512.png": 512,
    }
    
    for filename, size in sizes.items():
        data = create_png(size, size, make_favicon_pixel)
        filepath = os.path.join(base_dir, filename)
        with open(filepath, "wb") as f:
            f.write(data)
        # Also save in assets/
        assets_filepath = os.path.join(base_dir, "assets", filename)
        with open(assets_filepath, "wb") as f:
            f.write(data)
        print(f"Generated {filename} ({size}x{size}) -> {len(data)} bytes")

    # Generate a standard .ico file containing 16x16 and 32x32 PNGs
    # ICO format header:
    # 0-1: reserved 0
    # 2-3: type 1 (icon)
    # 4-5: count (2)
    p16 = create_png(16, 16, make_favicon_pixel)
    p32 = create_png(32, 32, make_favicon_pixel)
    
    ico_header = struct.pack("<HHH", 0, 1, 2)
    # Directory entry 1: 16x16
    # Width, Height, Colors (0), Reserved (0), Planes (1), BitCount (32), SizeInBytes, Offset
    offset_1 = 6 + 16 * 2
    entry_1 = struct.pack("<BBBBHHII", 16, 16, 0, 0, 1, 32, len(p16), offset_1)
    
    offset_2 = offset_1 + len(p16)
    entry_2 = struct.pack("<BBBBHHII", 32, 32, 0, 0, 1, 32, len(p32), offset_2)
    
    ico_data = ico_header + entry_1 + entry_2 + p16 + p32
    ico_path = os.path.join(base_dir, "favicon.ico")
    with open(ico_path, "wb") as f:
        f.write(ico_data)
    with open(os.path.join(base_dir, "assets", "favicon.ico"), "wb") as f:
        f.write(ico_data)
    print(f"Generated favicon.ico -> {len(ico_data)} bytes")

if __name__ == "__main__":
    main()
