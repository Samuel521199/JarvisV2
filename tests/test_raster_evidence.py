"""Independent image oracle and malformed-input coverage; Pillow is test-only."""
import random
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from sdk.raster import Raster, Board, load_png, SIGNATURE
from modules.skills.studio3d.paired_review import make_sheet


def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))


def png(w,h,depth,color,data,extras=b'',interlace=0):
    return SIGNATURE+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,depth,color,0,0,interlace))+extras+chunk(b'IDAT',zlib.compress(data))+chunk(b'IEND',b'')


class RasterEvidence(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_all_filters_rgb_rgba_independent_pillow_pixels_and_crop_roundtrip(self):
        from PIL import Image
        rng=random.Random(71)
        for channels in (3,4):
            for mode in range(5):
                width,height=31,17;raw=bytes(rng.randrange(256) for _ in range(width*height*channels));encoded=bytearray();stride=width*channels
                for y in range(height):
                    encoded.append(mode)
                    for x in range(stride):
                        value=raw[y*stride+x];a=raw[y*stride+x-channels] if x>=channels else 0
                        b=raw[(y-1)*stride+x] if y else 0;c=raw[(y-1)*stride+x-channels] if y and x>=channels else 0
                        p=a+b-c;dist=[abs(p-a),abs(p-b),abs(p-c)];predict=(a,b,c)[dist.index(min(dist))]
                        encoded.append((value-(0 if mode==0 else a if mode==1 else b if mode==2 else (a+b)//2 if mode==3 else predict))&255)
                path=self.root/f'{channels}-{mode}.png';path.write_bytes(png(width,height,8,2 if channels==3 else 6,encoded))
                decoded=load_png(path);self.assertEqual(decoded.pixels,raw)
                with Image.open(path) as image:self.assertEqual(decoded.pixels,image.tobytes())
                crop=decoded.crop((3,2,20,14));crop.save(self.root/'crop.png')
                with Image.open(self.root/'crop.png') as image:self.assertEqual(image.tobytes(),crop.pixels)
                self.assertEqual(load_png(self.root/'crop.png'),crop)

    def test_packed_palette_grayscale_alpha_and_16_bit(self):
        from PIL import Image
        fixtures=[png(4,1,2,3,b'\0\x1b',chunk(b'PLTE',bytes([255,0,0,0,255,0,0,0,255,0,0,0]))+chunk(b'tRNS',bytes([255,128,0,255]))),
                  png(8,1,1,0,b'\0\xa5'),png(2,1,8,4,b'\0\x12\xff\x80\x40'),
                  png(2,1,16,2,b'\0'+struct.pack('>6H',0,65535,0x1234,0x8888,0x7777,0xeeee)),
                  png(2,1,8,2,b'\0\x01\x02\x03\x04\x05\x06',chunk(b'tRNS',struct.pack('>3H',1,2,3)))]
        for i,raw in enumerate(fixtures):
            path=self.root/f'fixture{i}.png';path.write_bytes(raw);decoded=load_png(path)
            with Image.open(path) as image:self.assertEqual(decoded.pixels,image.convert('RGBA' if decoded.channels==4 else 'RGB').tobytes())

    def test_adam7_non_square_pass_placement(self):
        from PIL import Image
        w,h=13,11;raw=bytes((i*71)%256 for i in range(w*h*3));data=bytearray()
        for x0,y0,dx,dy in ((0,0,8,8),(4,0,8,8),(0,4,4,8),(2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2)):
            for y in range(y0,h,dy):
                if x0>=w:continue
                data.append(0)
                for x in range(x0,w,dx):data.extend(raw[(y*w+x)*3:(y*w+x+1)*3])
        path=self.root/'interlaced.png';path.write_bytes(png(w,h,8,2,data,interlace=1))
        self.assertEqual(load_png(path).pixels,raw)
        with Image.open(path) as image:self.assertEqual(image.tobytes(),raw)

    def test_crc_truncation_overexpansion_unknown_critical_and_budgets_rejected(self):
        valid=png(2,1,8,2,b'\0'+b'\xff'*6)
        invalid=[valid[:-1],valid+b'extra',valid[:32]+bytes([valid[32]^1])+valid[33:],
                 png(1,1,8,2,b'\0'+b'\0'*10000),png(1,1,8,2,b'\5\0\0\0'),
                 png(1,1,8,2,b'\0\0\0\0',chunk(b'FAIL',b'')),png(1,1,8,3,b'\0\0')]
        for raw in invalid:
            path=self.root/'bad.png';path.write_bytes(raw)
            with self.assertRaises(ValueError):load_png(path)
        path=self.root/'good.png';path.write_bytes(valid)
        with self.assertRaises(ValueError):load_png(path,max_pixels=1)
        with self.assertRaises(ValueError):load_png(path).crop((-1,0,1,1))

    def test_paired_sheet_preserves_both_original_rgb_regions(self):
        before=self.root/'before.png';after=self.root/'after.png';out=self.root/'sheet.png'
        a=Raster(64,47,3,bytes([9,17,129])*64*47);b=Raster(64,47,4,bytes([240,71,13,61])*64*47)
        a.save(before);b.save(after);report=make_sheet(before,after,out);sheet=load_png(out)
        self.assertEqual(sheet.crop((0,32,64,79)),a)
        self.assertEqual(sheet.crop((0,111,64,158)),b.rgb())
        self.assertEqual(report['size'],[64,158])
        other=self.root/'other.png';Raster(2,2,3,b'\0'*12).save(other)
        with self.assertRaises(ValueError):make_sheet(before,other,out)

    def test_board_resize_mirror_and_no_hidden_content_edits(self):
        source=Raster(2,1,3,bytes([1,2,3,4,5,6]));board=Board(5,3)
        self.assertEqual(source.mirrored().pixels,bytes([4,5,6,1,2,3]))
        board.paste(source.resized(4,2),1,1)
        self.assertEqual(board.image().crop((1,1,5,3)).pixels,bytes([1,2,3]*2+[4,5,6]*2)*2)
        with self.assertRaises(ValueError):board.paste(source,4,0)
