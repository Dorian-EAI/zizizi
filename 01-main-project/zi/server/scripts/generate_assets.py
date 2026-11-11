import os
import struct
import zlib


def create_png(width, height, rgb_color):
    r, g, b = rgb_color

    signature = b'\x89PNG\r\n\x1a\n'

    def chunk(chunk_type, data):
        chunk_len = struct.pack('>I', len(data))
        chunk_type_bytes = chunk_type.encode('ascii')
        crc_data = chunk_type_bytes + data
        crc = struct.pack('>I', zlib.crc32(crc_data) & 0xffffffff)
        return chunk_len + chunk_type_bytes + data + crc

    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = chunk('IHDR', ihdr_data)

    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'
        for x in range(width):
            raw_data += bytes([r, g, b])

    compressed = zlib.compress(raw_data, 9)
    idat = chunk('IDAT', compressed)

    iend = chunk('IEND', b'')

    return signature + ihdr + idat + iend


ASSETS = [
    ('default-avatar.png', (0x88, 0x88, 0x88)),
    ('marker.png', (0xe6, 0x43, 0x40)),
    ('marker-green.png', (0x10, 0xB9, 0x81)),
    ('marker-red.png', (0xe6, 0x43, 0x40)),
    ('tab-home.png', (0x99, 0x99, 0x99)),
    ('tab-home-active.png', (0x00, 0x40, 0x80)),
    ('tab-publish.png', (0x99, 0x99, 0x99)),
    ('tab-publish-active.png', (0x00, 0x40, 0x80)),
    ('tab-order.png', (0x99, 0x99, 0x99)),
    ('tab-order-active.png', (0x00, 0x40, 0x80)),
    ('tab-mine.png', (0x99, 0x99, 0x99)),
    ('tab-mine-active.png', (0x00, 0x40, 0x80)),
]


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    client_dir = os.path.join(os.path.dirname(project_root), 'client')
    assets_dir = os.path.join(client_dir, 'assets')

    os.makedirs(assets_dir, exist_ok=True)
    print(f'Assets directory: {assets_dir}')

    size = 48
    generated = []

    for filename, color in ASSETS:
        filepath = os.path.join(assets_dir, filename)
        png_bytes = create_png(size, size, color)
        with open(filepath, 'wb') as f:
            f.write(png_bytes)
        generated.append(filepath)
        print(f'  Created: {filename} ({os.path.getsize(filepath)} bytes, RGB{color})')

    print(f'\nTotal {len(generated)} assets generated successfully.')
    return generated


if __name__ == '__main__':
    main()
