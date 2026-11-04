"""Bounded standard-library PNG operations for render evidence and review boards.

No network, native libraries or operating-system font dependency. Evidence crops
preserve decoded sample bytes; review-board resizing is an explicit operation.
"""
from dataclasses import dataclass
import struct
import zlib
from pathlib import Path

SIGNATURE = b'\x89PNG\r\n\x1a\n'
MAX_BYTES = 96 * 1024**2


@dataclass(frozen=True)
class Raster:
    width: int
    height: int
    channels: int
    pixels: bytes

    def __post_init__(self):
        if self.channels not in (3, 4) or min(self.width, self.height) < 1 or len(self.pixels) != self.width*self.height*self.channels or len(self.pixels) > MAX_BYTES:
            raise ValueError('Invalid raster dimensions or pixel budget')

    @property
    def size(self):
        return (self.width, self.height)

    def crop(self, rect):
        x0, y0, x1, y1 = rect
        if any(type(x) is not int for x in rect) or not (0 <= x0 < x1 <= self.width and 0 <= y0 < y1 <= self.height):
            raise ValueError('Crop outside original image')
        stride = self.width*self.channels
        return Raster(x1-x0, y1-y0, self.channels, b''.join(self.pixels[y*stride+x0*self.channels:y*stride+x1*self.channels] for y in range(y0, y1)))

    def rgb(self):
        return self if self.channels == 3 else Raster(self.width, self.height, 3, b''.join(self.pixels[i:i+3] for i in range(0,len(self.pixels),4)))

    def resized(self, width, height):
        if width*height*self.channels > MAX_BYTES or min(width,height) < 1:
            raise ValueError('Resize budget')
        # Nearest neighbour is used only for explicitly labelled preview boards.
        out = bytearray(width*height*self.channels)
        for y in range(height):
            sy = min(self.height-1, int((y+.5)*self.height/height))
            for x in range(width):
                sx = min(self.width-1, int((x+.5)*self.width/width))
                at = (y*width+x)*self.channels; source = (sy*self.width+sx)*self.channels
                out[at:at+self.channels] = self.pixels[source:source+self.channels]
        return Raster(width,height,self.channels,bytes(out))

    def mirrored(self):
        c=self.channels; stride=self.width*c
        return Raster(self.width,self.height,c,b''.join(self.pixels[y*stride+x*c:y*stride+(x+1)*c] for y in range(self.height) for x in range(self.width-1,-1,-1)))

    def save(self, path):
        def chunk(kind, data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
        stride=self.width*self.channels
        data=b''.join(b'\0'+self.pixels[i:i+stride] for i in range(0,len(self.pixels),stride))
        raw=SIGNATURE+chunk(b'IHDR',struct.pack('>IIBBBBB',self.width,self.height,8,2 if self.channels==3 else 6,0,0,0))+chunk(b'IDAT',zlib.compress(data))+chunk(b'IEND',b'')
        Path(path).write_bytes(raw)


def _paeth(a,b,c):
    p=a+b-c; pa=abs(p-a); pb=abs(p-b); pc=abs(p-c)
    return a if pa<=pb and pa<=pc else b if pb<=pc else c


def load_png(path, *, max_pixels=20_000_000):
    path=Path(path)
    if path.stat().st_size>MAX_BYTES:raise ValueError('PNG file budget')
    raw=path.read_bytes()
    if not raw.startswith(SIGNATURE):raise ValueError('PNG required')
    at=8; chunks=[]; compressed=bytearray(); palette=None; transparency=None; ended=False; idat_ended=False
    while at<len(raw):
        if at+12>len(raw):raise ValueError('Truncated PNG chunk')
        size=struct.unpack_from('>I',raw,at)[0]; kind=raw[at+4:at+8]; end=at+8+size
        if end+4>len(raw) or size>MAX_BYTES:raise ValueError('Truncated PNG data')
        value=raw[at+8:end]
        if zlib.crc32(kind+value)!=struct.unpack_from('>I',raw,end)[0]:raise ValueError('PNG CRC mismatch')
        if not chunks and kind!=b'IHDR':raise ValueError('IHDR must be first')
        if kind==b'IHDR':
            if chunks or size!=13:raise ValueError('Invalid PNG header')
            w,h,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',value)
            channels={0:1,2:3,3:1,4:2,6:4}.get(color)
            valid_depths={0:{1,2,4,8,16},2:{8,16},3:{1,2,4,8},4:{8,16},6:{8,16}}
            if not channels or depth not in valid_depths[color] or min(w,h)<1 or w*h>max_pixels or w*h*4>MAX_BYTES or compression or filtering or interlace not in (0,1):raise ValueError('Unsupported PNG header or budget')
        elif kind==b'PLTE':
            if palette is not None or b'IDAT' in chunks or not size or size%3 or size>768:raise ValueError('Invalid PNG palette')
            palette=[tuple(value[i:i+3]) for i in range(0,size,3)]
        elif kind==b'tRNS':
            if transparency is not None or b'IDAT' in chunks or color not in (0,2,3):raise ValueError('Invalid PNG transparency')
            transparency=value
        elif kind==b'IDAT':
            if idat_ended:raise ValueError('Non-contiguous PNG data')
            compressed.extend(value)
        elif kind==b'IEND':
            if size or end+4!=len(raw) or b'IDAT' not in chunks:raise ValueError('Invalid PNG ending')
            ended=True;break
        elif kind[0]&32==0:raise ValueError('Unknown critical PNG chunk')
        if kind!=b'IDAT' and b'IDAT' in chunks:idat_ended=True
        chunks.append(kind);at=end+4
    if not ended:raise ValueError('Missing PNG end')
    if color==3 and (palette is None or len(palette)>2**depth):raise ValueError('Missing or invalid PNG palette')
    if transparency is not None and ((color==0 and len(transparency)!=2) or (color==2 and len(transparency)!=6) or (color==3 and len(transparency)>len(palette))):raise ValueError('Invalid PNG alpha samples')
    passes=[(0,0,1,1)] if not interlace else [(0,0,8,8),(4,0,8,8),(0,4,4,8),(2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2)]
    dimensions=[(x,y,dx,dy,max(0,(w-x+dx-1)//dx),max(0,(h-y+dy-1)//dy)) for x,y,dx,dy in passes]
    expected=sum(ph*(1+(pw*channels*depth+7)//8) for _,_,_,_,pw,ph in dimensions if pw and ph)
    if expected>MAX_BYTES*2:raise ValueError('PNG inflation budget')
    decoder=zlib.decompressobj(); data=decoder.decompress(compressed,expected+1)
    if len(data)!=expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('PNG decompressed size mismatch')
    alpha=color in (4,6) or transparency is not None; outc=4 if alpha else 3
    out=bytearray(w*h*outc); position=0; bpp=max(1,(channels*depth+7)//8)
    transparent=struct.unpack('>'+('H'*(len(transparency)//2)),transparency) if transparency is not None and color!=3 else None
    for x0,y0,dx,dy,pw,ph in dimensions:
        if not pw or not ph:continue
        stride=(pw*channels*depth+7)//8; prior=bytearray(stride)
        for y in range(ph):
            mode=data[position];position+=1;row=bytearray(data[position:position+stride]);position+=stride
            if mode not in range(5):raise ValueError('Invalid PNG filter')
            if mode==2:row=bytearray((a+b)&255 for a,b in zip(row,prior))
            elif mode:
                for i in range(stride):
                    a=row[i-bpp] if i>=bpp else 0;b=prior[i];c=prior[i-bpp] if i>=bpp else 0
                    row[i]=(row[i]+(a if mode==1 else (a+b)//2 if mode==3 else _paeth(a,b,c)))&255
            if depth==8 and color in (2,6) and transparency is None and dx==1:
                target=((y0+y*dy)*w+x0)*outc
                out[target:target+len(row)]=row;prior=row;continue
            if depth==8:samples=row
            elif depth==16:samples=struct.unpack('>'+'H'*(len(row)//2),row)
            else:samples=[(row[i*depth//8]>>(8-depth-(i*depth%8)))&((1<<depth)-1) for i in range(pw*channels)]
            for x in range(pw):
                v=samples[x*channels:(x+1)*channels]
                if color==3:
                    if v[0]>=len(palette):raise ValueError('PNG palette index')
                    pixel=palette[v[0]]+((transparency[v[0]] if v[0]<len(transparency) else 255,) if alpha else ())
                else:
                    scale=lambda sample:sample>>8 if depth==16 else sample*255//((1<<depth)-1)
                    rgb=(v[0],)*3 if color in (0,4) else tuple(v[:3]);pixel=tuple(scale(n) for n in rgb)
                    if alpha:pixel+=(scale(v[-1]) if color in (4,6) else 0 if tuple(v)==transparent else 255,)
                target=((y0+y*dy)*w+x0+x*dx)*outc;out[target:target+outc]=bytes(pixel)
            prior=row
    return Raster(w,h,outc,bytes(out))


class Board:
    def __init__(self, width,height, background=(245,245,245)):
        if width*height*3>MAX_BYTES or min(width,height)<1:raise ValueError('Board budget')
        self.width=width;self.height=height;self.pixels=bytearray(bytes(background)*width*height)

    def paste(self, image,x,y):
        image=image.rgb()
        if x<0 or y<0 or x+image.width>self.width or y+image.height>self.height:raise ValueError('Board bounds')
        for row in range(image.height):
            at=((y+row)*self.width+x)*3;source=row*image.width*3
            self.pixels[at:at+image.width*3]=image.pixels[source:source+image.width*3]

    def image(self):return Raster(self.width,self.height,3,bytes(self.pixels))

    def text(self, x,y,text, *, color=(0,0,0), scale=2):
        # Small original bitmap alphabet: labels remain portable and explicit.
        for char in text.upper():
            rows=_FONT.get(char,_FONT['?'])
            for row,bits in enumerate(rows):
                for col in range(5):
                    if bits & (1<<(4-col)):
                        for sy in range(scale):
                            for sx in range(scale):
                                px=x+col*scale+sx;py=y+row*scale+sy
                                if 0<=px<self.width and 0<=py<self.height:
                                    at=(py*self.width+px)*3;self.pixels[at:at+3]=bytes(color)
            x+=6*scale


_FONT={c:tuple(int(row,16) for row in rows.split()) for c,rows in {
 'A':'0e 11 11 1f 11 11 11','B':'1e 11 11 1e 11 11 1e','C':'0e 11 10 10 10 11 0e',
 'D':'1e 11 11 11 11 11 1e','E':'1f 10 10 1e 10 10 1f','F':'1f 10 10 1e 10 10 10',
 'G':'0e 11 10 17 11 11 0f','H':'11 11 11 1f 11 11 11','I':'1f 04 04 04 04 04 1f',
 'J':'07 02 02 02 12 12 0c','K':'11 12 14 18 14 12 11','L':'10 10 10 10 10 10 1f',
 'M':'11 1b 15 15 11 11 11','N':'11 19 15 13 11 11 11','O':'0e 11 11 11 11 11 0e',
 'P':'1e 11 11 1e 10 10 10','Q':'0e 11 11 11 15 12 0d','R':'1e 11 11 1e 14 12 11',
 'S':'0f 10 10 0e 01 01 1e','T':'1f 04 04 04 04 04 04','U':'11 11 11 11 11 11 0e',
 'V':'11 11 11 11 11 0a 04','W':'11 11 11 15 15 1b 11','X':'11 11 0a 04 0a 11 11',
 'Y':'11 11 0a 04 04 04 04','Z':'1f 01 02 04 08 10 1f','0':'0e 11 13 15 19 11 0e',
 '1':'04 0c 04 04 04 04 0e','2':'0e 11 01 02 04 08 1f','3':'1e 01 01 0e 01 01 1e',
 '4':'02 06 0a 12 1f 02 02','5':'1f 10 10 1e 01 01 1e','6':'0e 10 10 1e 11 11 0e',
 '7':'1f 01 02 04 08 08 08','8':'0e 11 11 0e 11 11 0e','9':'0e 11 11 0f 01 01 0e',
 ' ':'00 00 00 00 00 00 00','-':'00 00 00 1f 00 00 00','/':'01 02 02 04 08 08 10',
 '(':'02 04 08 08 08 04 02',')':'08 04 02 02 02 04 08','?':'0e 11 01 02 04 00 04',
 '.':'00 00 00 00 00 0c 0c',':':'00 0c 0c 00 0c 0c 00'}.items()}
