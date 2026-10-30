"""Make a labelled board from the user's concept and real Blender renders."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

out=Path('D:/Jarvis/user-data/artifacts/studio3d-character/silver-hair-rebuild-study-03')
source=Path('C:/Users/samuel/Desktop/人物美术核心概念MD与图片_31份/images/0cac840e58f32ebca523.png')
ref=Image.open(source).convert('RGB')
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
canvas=Image.new('RGB',(1536,1092),(36,40,49));draw=ImageDraw.Draw(canvas)
titles=['REFERENCE CONCEPT / FRONT','REFERENCE CONCEPT / 45','REFERENCE CONCEPT / SIDE',
        'BLENDER RENDER / FRONT','BLENDER RENDER / 45 (MIRRORED)','BLENDER RENDER / SIDE (MIRRORED)']
for i,title in enumerate(titles):
    x=(i%3)*512;y=(i//3)*546
    draw.text((x+8,y+6),title,font=font,fill='white')
    if i<3:
        image=ref.crop((i*512,504,(i+1)*512,1016)).resize((512,512))
    else:
        image=Image.open(out/[ 'front.png','oblique.png','side.png'][i-3]).convert('RGB').resize((512,512))
        if i>3:image=ImageOps.mirror(image)
    canvas.paste(image,(x,y+34))
canvas.save(out/'hair-reference-comparison.png')
