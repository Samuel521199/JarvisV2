"""Create an approximate smooth rear-hair shell from hand-read image outlines."""
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.measure import marching_cubes
root=Path(__file__).resolve().parents[1];out=root/'user-data/artifacts/studio3d-character/hair-profile-study-01'
if out.exists():raise ValueError('Existing study requires inspection')
out.mkdir(parents=True)
# Approximate silhouette positions on the supplied 1024x1536 images. These are
# deliberate fit assumptions, not measured 3-D geometry.
rows=np.array([130,145,165,190,220,250,280,310,340,360,378,390])
rear_half_width=np.array([12,48,70,87,98,101,96,96,95,86,58,0])
side_rear_depth=np.array([25,45,69,82,89,92,98,98,96,86,75,0])
scale=1335/1.6
X=np.linspace(-.145,.145,168);Y=np.linspace(0,.145,168);Z=np.linspace(1.285,1.60,192)
pixels=130+(1.6-Z)*scale
w=np.interp(pixels,rows,rear_half_width)/scale;d=np.interp(pixels,rows,side_rear_depth)/scale
ratio=np.abs(X[None,:])/np.maximum(w[:,None],.0001)
cap=np.sqrt(np.maximum(0,1-np.minimum(1,ratio)**2))*d[:,None]
volume=(ratio[:,None,:]<1)&(Y[None,:,None]<cap[:,None,:])&(w[:,None,None]>.002)&(d[:,None,None]>.002)
# At neck height retain a hollow space for the head and neck rather than
# filling the entire back of the character with an opaque solid.
neck=((X[None,:]/.053)**2+(Y[:,None]/.047)**2)<1
lower=(Z<1.405)[:,None,None]
volume &= ~(lower&neck[None,:,:])
field=gaussian_filter(volume.astype(np.float32),sigma=(1.6,1.6,1.6))
verts,faces,_,_=marching_cubes(field,level=.5,spacing=(Z[1]-Z[0],Y[1]-Y[0],X[1]-X[0]))
verts[:,0]+=Z[0];verts[:,1]+=Y[0];verts[:,2]+=X[0]
with (out/'rear-hair.obj').open('w',encoding='utf8') as f:
 for z,y,x in verts:f.write(f'v {x:.7f} {y:.7f} {z:.7f}\n')
 for a,b,c in faces+1:f.write(f'f {a} {b} {c}\n')
(out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','vertices':len(verts),'faces':len(faces),
 'method':'approximate hand-read front/rear silhouette plus ellipsoid cross-section and neck hollow',
 'limits':['Manually estimated silhouettes and camera','No layered strands','No animation or collision validation']},indent=2),encoding='utf8')
print('PROFILE_READY',len(verts),'vertices',len(faces),'triangles')
