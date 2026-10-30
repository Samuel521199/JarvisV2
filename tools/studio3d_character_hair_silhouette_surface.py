"""Fit a smooth rear hair volume to approximate reference outer silhouettes."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_closing,binary_opening,gaussian_filter,gaussian_filter1d
from skimage.measure import marching_cubes
root=Path(__file__).resolve().parents[1];refs=Path('C:/Users/samuel/Desktop/模型')
out=root/'user-data/artifacts/studio3d-character/hair-reference-surface-01'
if out.exists():raise ValueError('Existing study requires inspection')
out.mkdir(parents=True)
def mask(name):
 a=np.asarray(Image.open(refs/name).convert('RGB')).astype(np.int16);r,g,b=a[:,:,0],a[:,:,1],a[:,:,2]
 return binary_opening(binary_closing((r-g>=-3)&(r-g<=6)&(b-r>=-5)&(r>135)&
   (abs(r-143)+abs(g-150)+abs(b-157)>9),iterations=3),iterations=1)
rear=mask('后.png');side=mask('右.png');scale=1335/1.6
X=np.linspace(-.155,.155,176);Y=np.linspace(0,.155,176);Z=np.linspace(1.295,1.60,200)
rows=np.clip(np.rint(130+(1.6-Z)*scale).astype(int),0,1535)
width=[];depth=[]
for row in rows:
 rear_x=np.where(rear[row,300:700])[0]+300;side_x=np.where(side[row,300:512])[0]+300
 width.append(max(abs(rear_x-512))/scale if len(rear_x)>4 else 0.)
 depth.append((512-min(side_x))/scale if len(side_x)>4 else 0.)
width=gaussian_filter1d(np.array(width),sigma=3);depth=gaussian_filter1d(np.array(depth),sigma=3)
ratio=np.abs(X[None,:])/np.maximum(width[:,None],.0001)
cap=np.sqrt(np.maximum(0,1-np.minimum(1,ratio)**2))*depth[:,None]
volume=(ratio[:,None,:]<1)&(Y[None,:,None]<cap[:,None,:])&(width[:,None,None]>.005)&(depth[:,None,None]>.005)
field=gaussian_filter(volume.astype(np.float32),sigma=(2.0,1.4,1.4))
verts,faces,_,_=marching_cubes(field,level=.5,spacing=(Z[1]-Z[0],Y[1]-Y[0],X[1]-X[0]))
verts[:,0]+=Z[0];verts[:,1]+=Y[0];verts[:,2]+=X[0]
with (out/'rear-hair.obj').open('w',encoding='utf8') as f:
 for z,y,x in verts:f.write(f'v {x:.7f} {y:.7f} {z:.7f}\n')
 for a,b,c in faces+1:f.write(f'f {a} {b} {c}\n')
(out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','vertices':len(verts),'faces':len(faces),
 'source_sha256':{n:hashlib.sha256((refs/n).read_bytes()).hexdigest() for n in ('后.png','右.png')},
 'method':'smoothed rear and side outer silhouettes with inferred ellipsoid cross section',
 'limits':['Assumed projection and dimensions','Smooth volume omits individual strands','No animation or shape accuracy validation']},indent=2),encoding='utf8')
print('SURFACE_READY',len(verts),'vertices',len(faces),'triangles')
