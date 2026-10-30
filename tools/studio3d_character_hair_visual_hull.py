"""Create a local rear-hair silhouette volume from user reference images.

This is a bounded geometric study, not a recovered original mesh. Image masks,
camera placement and scale are approximate and must be verified visually.
"""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_closing,binary_opening,gaussian_filter
from skimage.measure import marching_cubes

root=Path(__file__).resolve().parents[1]
refs=Path('C:/Users/samuel/Desktop/模型')
out=root/'user-data/artifacts/studio3d-character/hair-reference-hull-01'
if out.exists():raise ValueError('Existing study requires inspection')
out.mkdir(parents=True)

def mask(name):
 a=np.asarray(Image.open(refs/name).convert('RGB')).astype(np.int16)
 r,g,b=a[:,:,0],a[:,:,1],a[:,:,2]
 pixels=(r-g>=-3)&(r-g<=6)&(b-r>=-5)&(r>135)&(abs(r-143)+abs(g-150)+abs(b-157)>9)
 pixels=binary_opening(binary_closing(pixels,iterations=3),iterations=1)
 return pixels

rear=mask('后.png');side=mask('右.png')
scale=1335/1.6
X=np.linspace(-.155,.155,176);Y=np.linspace(0,.155,176);Z=np.linspace(1.295,1.485,144)
px=np.clip(np.rint(512-X*scale).astype(int),0,1023)
py=np.clip(np.rint(512-Y*scale).astype(int),0,1023)
pz=np.clip(np.rint(130+(1.6-Z)*scale).astype(int),0,1535)
volume=rear[pz[:,None],px[None,:]][:,None,:]&side[pz[:,None],py[None,:]][:,:,None]
# Soften pixel noise without claiming unseen surfaces are known.
volume=binary_closing(volume,iterations=2)
field=gaussian_filter(volume.astype(np.float32),sigma=1.15)
if field.max()<.5:raise ValueError('No reference silhouette')
verts,faces,_,_=marching_cubes(field,level=.5,spacing=(Z[1]-Z[0],Y[1]-Y[0],X[1]-X[0]))
verts[:,0]+=Z[0];verts[:,1]+=Y[0];verts[:,2]+=X[0]
with (out/'rear-hair.obj').open('w',encoding='utf8') as f:
 for z,y,x in verts:f.write(f'v {x:.7f} {y:.7f} {z:.7f}\n')
 for a,b,c in faces+1:f.write(f'f {a} {b} {c}\n')
(out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','vertices':len(verts),'faces':len(faces),
 'source_sha256':{n:hashlib.sha256((refs/n).read_bytes()).hexdigest() for n in ('后.png','右.png')},
 'scale_assumptions':{'image_head_top_y':130,'image_height_pixels':1335,'model_height_m':1.6,'side_center_x':512},
 'limitations':['Image-derived binary masks and guessed camera alignment','Inferred occluded geometry','No material/rig/animation acceptance']},
 ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('HULL_READY',len(verts),'vertices',len(faces),'triangles')
