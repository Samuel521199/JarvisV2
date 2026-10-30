"""Label actual old/new renders without painting or generating model imagery."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path('D:/Jarvis/user-data/artifacts/studio3d-character')
old=root/'silver-hair-rebuild-study-03';new=root/'character-authoring-hair-03'
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
board=Image.new('RGB',(1536,1104),(34,37,44));draw=ImageDraw.Draw(board)
for row,folder in enumerate((old,new)):
    for col,view in enumerate(('front','oblique','rear')):
        x=col*512;y=row*552
        draw.text((x+10,y+8),('BEFORE' if row==0 else 'NEW SKILL / CURRENT')+' - '+view.upper(),font=font,fill='white')
        img=Image.open(folder/(view+'.png')).convert('RGB').resize((512,512))
        board.paste(img,(x,y+40))
board.save(new/'before-after.png')
