"""Label actual old/new renders; explicit nearest-neighbour preview scaling."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sdk.runtime_paths import project_path, option
from sdk.raster import load_png, Board


def main():
    root=project_path('user-data/artifacts/studio3d-character')
    old=Path(option('--before') or root/'silver-hair-rebuild-study-03')
    new=Path(option('--after') or root/'character-authoring-hair-03')
    board=Board(1536,1104,(34,37,44))
    for row,folder in enumerate((old,new)):
        for col,view in enumerate(('front','oblique','rear')):
            x=col*512;y=row*552
            board.text(x+10,y+8,('BEFORE' if row==0 else 'NEW SKILL / CURRENT')+' - '+view, color=(255,255,255))
            board.paste(load_png(folder/(view+'.png')).rgb().resized(512,512),x,y+40)
    board.image().save(Path(option('--output') or new/'before-after.png'))


if __name__=='__main__':main()
