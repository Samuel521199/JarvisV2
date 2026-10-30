"""Apply the reusable character-authoring skill to this asset's hair guides."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
TOOL=Path('C:/Users/samuel/.codex/skills/blender-character-authoring/scripts/character_tools.py')
spec=importlib.util.spec_from_file_location('character_authoring_tools',TOOL)
tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(tools)
source=ROOT/'user-data/artifacts/studio3d-character/silver-hair-rebuild-study-03/candidate.blend'
out=ROOT/'user-data/artifacts/studio3d-character/character-authoring-hair-03'
if out.exists():raise ValueError('Trial exists')
out.mkdir(parents=True)
binding={'armature':'Armature','bone':'J_Bip_C_Head'}
ops=[]

def lock(name,points,widths,across=(1,0,0),mat='AuthorSilver',depth=.12):
    ops.append({'type':'hair_lock','name':'Author_'+name,'points':points,'widths':widths,
                'across':across,'material':mat,'depth_ratio':depth,'binding':binding})

# A restrained underlayer covers scalp between roots; it is separate from the head.
vs=[];fs=[];rings=18;columns=72
for j in range(rings):
    for i in range(columns):
        a=i*2*math.pi/columns
        end=1.45+.65*math.sin(a)
        theta=.025+(end-.025)*j/(rings-1)
        vs.append([.1005*math.sin(theta)*math.cos(a),.024+.115*math.sin(theta)*math.sin(a),1.497+.105*math.cos(theta)])
for j in range(rings-1):
    for i in range(columns):
        n=j*columns+i;k=j*columns+(i+1)%columns
        fs.append([n,k,k+columns,n+columns])
fs.append(list(reversed(range(columns))))
ops.append({'type':'mesh','name':'Author_ScalpUnderlayer','vertices':vs,'faces':fs,'binding':binding,'material':'AuthorSilverSoft'})

# The guide values are hand-authored approximations from the user's concept.
# Each back guide follows the skull before a broad, shallow S-shaped lower sweep.
for layer in range(2):
    count=19 if layer==0 else 13
    for k in range(count):
        a=.02+(math.pi-.04)*(k+.30*layer)/(count-1+.30*layer)
        c,s=math.cos(a),math.sin(a);phase=math.sin(k*1.72+layer)
        points=[]
        for theta in (.10,.43,.86,1.28,1.68):
            points.append([(.105+.002*layer)*math.sin(theta)*c,
                           .024+(.120+.003*layer)*math.sin(theta)*s,
                           1.497+(.109+.002*layer)*math.cos(theta)])
        z=1.19+.012*phase+.050*layer
        points.extend([[.115*c,.035+.126*s,1.414],[.136*c+.004*phase,.042+.133*s,1.333],
                       [.149*c+.006*phase,.047+.130*s,z+.050],[.157*c+.007*phase,.052+.126*s,z]])
        w=.018 if layer==0 else .014
        lock('Back_%s_%02d'%(layer,k),points,[.002,.008,.013,w,w,w*.95,w*.7,w*.3,.00012],(-s,c,0),
             'AuthorSilverSoft' if layer else 'AuthorSilver',.10)

# Large swept front locks overlap; tip heights deliberately differ.
fringe=[
    ([[-.003,-.018,1.606],[-.016,-.057,1.594],[-.012,-.089,1.562],[.004,-.103,1.507],[.018,-.099,1.470]], [.004,.015,.021,.014,.00012]),
    ([[-.013,-.012,1.604],[-.032,-.054,1.589],[-.044,-.088,1.549],[-.057,-.099,1.500],[-.073,-.086,1.474]], [.004,.015,.018,.012,.00012]),
    ([[.007,-.011,1.605],[.028,-.053,1.590],[.043,-.088,1.550],[.057,-.100,1.507],[.074,-.085,1.488]], [.004,.017,.020,.012,.00012]),
    ([[-.008,-.020,1.608],[-.021,-.061,1.592],[-.028,-.096,1.548],[-.039,-.105,1.499],[-.046,-.099,1.464]], [.002,.007,.011,.008,.00010]),
    ([[.014,-.020,1.607],[.036,-.062,1.588],[.054,-.094,1.543],[.067,-.101,1.510],[.083,-.079,1.484]], [.002,.007,.010,.007,.00010]),
]
for k,(p,w) in enumerate(fringe):lock('Fringe_%02d'%k,p,w,mat='AuthorSilverBright' if k%2 else 'AuthorSilver',depth=.10)
lock('FringeSupport',[[.001,-.021,1.607],[-.005,-.062,1.592],[-.009,-.095,1.545],[-.012,-.104,1.501],[-.006,-.099,1.478]],
     [.003,.010,.013,.009,.00012],depth=.09)

for sign in (-1,1):
    # Crown side panels cover above the ears, flowing into long locks instead of short petals.
    for k in range(4):
        y=-.047+k*.029
        p=[[sign*.009,.010,1.605],[sign*.056,y*.50,1.594],[sign*.090,y,1.554],
           [sign*.107,y+.002,1.500],[sign*.114,y+.005,1.427],
           [sign*.119,y+.003,1.353],[sign*.128,y+.006,1.302+.014*k]]
        lock('SideCrown_%s_%02d'%(sign,k),p,[.003,.013,.020,.019,.016,.010,.00012],(0,1,0))
    # Longer face-framing sweep, positioned in front of the shoulder.
    for k in range(2):
        p=[[sign*.033,-.007,1.602],[sign*.073,-.051,1.568],[sign*(.091+.005*k),-.073,1.505],
           [sign*(.088+.009*k),-.078,1.437],[sign*(.079+.012*k),-.081,1.367],
           [sign*(.099+.012*k),-.086,1.310],[sign*(.135+.009*k),-.065,1.263+.014*k]]
        lock('FaceLong_%s_%02d'%(sign,k),p,[.003,.013,.016,.017,.014,.009,.00012],mat='AuthorSilverBright')
    # Short curved wisps sit at different cheek heights rather than straight needles.
    for k in range(2):
        p=[[sign*.073,-.061,1.547],[sign*.088,-.084,1.505],[sign*.087,-.091,1.469-.012*k],
           [sign*.071,-.093,1.442-.016*k],[sign*.057,-.086,1.437-.018*k]]
        lock('CheekWisp_%s_%02d'%(sign,k),p,[.002,.005,.006,.004,.00009],mat='AuthorSilverSoft',depth=.09)

plan={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'output':str(out/'candidate.blend'),'collection':'Hair_Authoring_Replaceable_03',
      'hide_collections':['Hair_SilverHair_Replaceable_01','Hair_Silver_Rebuild_Replaceable_Trial'],
      'protected_objects':['Face'],
      'materials':{name:{'color':color,'roughness':.39,'hair_detail':True} for name,color in
        [('AuthorSilver',[.75,.75,.81,1]),('AuthorSilverSoft',[.70,.70,.78,1]),('AuthorSilverBright',[.83,.82,.88,1])]},
      'operations':ops,'render':{'center':[0,0,1.405],'scale':.42,'size':900,'samples':32,
        'views':{'front':[0,-1,0],'oblique':[-.7071,-.7071,0],'side':[-1,0,0],'rear':[0,1,0]}}}
(out/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
with render_lane(out):tools.apply_plan(plan)
