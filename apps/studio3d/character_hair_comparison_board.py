"""Label concept/render previews; mirroring and resizing are explicit."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sdk.runtime_paths import project_path, reference_path, option
from sdk.raster import load_png, Board


def main():
    out=Path(option('--renders') or project_path('user-data/artifacts/studio3d-character/silver-hair-rebuild-study-03'))
    source=reference_path('人物美术核心概念MD与图片_31份/images/0cac840e58f32ebca523.png')
    ref=load_png(source).rgb();canvas=Board(1536,1092,(36,40,49))
    titles=['REFERENCE CONCEPT / FRONT','REFERENCE CONCEPT / 45','REFERENCE CONCEPT / SIDE',
            'BLENDER RENDER / FRONT','BLENDER RENDER / 45 (MIRRORED)','BLENDER RENDER / SIDE (MIRRORED)']
    for i,title in enumerate(titles):
        x=(i%3)*512;y=(i//3)*546
        canvas.text(x+8,y+6,title,color=(255,255,255))
        if i<3:image=ref.crop((i*512,504,(i+1)*512,1016)).resized(512,512)
        else:
            image=load_png(out/['front.png','oblique.png','side.png'][i-3]).rgb().resized(512,512)
            if i>3:image=image.mirrored()
        canvas.paste(image,x,y+34)
    canvas.image().save(Path(option('--output') or out/'hair-reference-comparison.png'))


if __name__=='__main__':main()
