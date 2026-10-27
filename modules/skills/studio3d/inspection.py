"""Read-only glTF inventory. File validity and production fitness are distinct."""
import json,struct,hashlib
from modules.skills.studio3d.assets import validate_glb,decode_upload

PROFILE={'id':'desktop-static-review-v1','name':'桌面静态资产检查基线','triangle_budget':100000,'texture_edge_budget':2048,
 'required_maps':['baseColor','normal','metallicRoughness','occlusion'],
 'human_checks':['轮廓与参考一致性','倒角与法线接缝','UV接缝和纹素密度','LOD轮廓与切换','授权来源和美术要求'],
 'scope':'A configurable review baseline, not a universal AAA standard or certification.'}

def document(raw):
    validate_glb(raw,max_bytes=128*1024**2);length=struct.unpack_from('<I',raw,12)[0];value=decode_upload(raw[20:20+length].rstrip(b' \x00'))
    pos=20+length;size,kind=struct.unpack_from('<II',raw,pos);assert kind==0x004e4942
    return value,raw[pos+8:pos+8+size]

def image_size(data,mime):
    if mime=='image/png' and data[:8]==b'\x89PNG\r\n\x1a\n' and len(data)>=24:return list(struct.unpack_from('>II',data,16))
    if mime=='image/jpeg' and data[:2]==b'\xff\xd8':
        i=2
        while i+9<len(data):
            if data[i]!=255:break
            marker=data[i+1];i+=2
            if marker in (0xd8,0xd9):continue
            length=int.from_bytes(data[i:i+2],'big')
            if length<2:break
            if marker in (0xc0,0xc1,0xc2):return [int.from_bytes(data[i+5:i+7],'big'),int.from_bytes(data[i+3:i+5],'big')]
            i+=length
    return None

def inspect(raw):
    doc,bin_=document(raw);images=[]
    for i,img in enumerate(doc.get('images',[])):
        view=doc['bufferViews'][img['bufferView']] if 'bufferView' in img else {};start=view.get('byteOffset',0);size=view.get('byteLength',0);dimensions=image_size(bin_[start:start+size],img.get('mimeType'))
        images.append({'index':i,'name':img.get('name','image-'+str(i)),'mime':img.get('mimeType'),'bytes':size,'dimensions':dimensions,'rgba_mip_estimate_bytes':round(dimensions[0]*dimensions[1]*4*4/3) if dimensions else None})
    mats=[];missing=[]
    for i,m in enumerate(doc.get('materials',[])):
        p=m.get('pbrMetallicRoughness',{});maps={k:bool(v) for k,v in [('baseColor',p.get('baseColorTexture')),('metallicRoughness',p.get('metallicRoughnessTexture')),('normal',m.get('normalTexture')),('occlusion',m.get('occlusionTexture')),('emissive',m.get('emissiveTexture'))]}
        absent=[k for k in PROFILE['required_maps'] if not maps[k]];missing.extend(absent)
        mats.append({'index':i,'name':m.get('name','material-'+str(i)),'baseColor':p.get('baseColorFactor',[1,1,1,1]),'metallic':p.get('metallicFactor',1),'roughness':p.get('roughnessFactor',1),'doubleSided':m.get('doubleSided',False),'maps':maps,'missing_for_profile':absent,'extensions':list(m.get('extensions',{}))})
    triangles=0;uv_missing=0;primitives=0
    for mesh in doc.get('meshes',[]):
        for p in mesh.get('primitives',[]):
            primitives+=1;count=doc['accessors'][p.get('indices',p['attributes']['POSITION'])]['count'];mode=p.get('mode',4)
            triangles+=count//3 if mode==4 else max(0,count-2) if mode in (5,6) else 0
            uv_missing+=int('TEXCOORD_0' not in p['attributes'])
    checks=[{'id':'triangle-budget','status':'pass' if triangles<=PROFILE['triangle_budget'] else 'warn','message':str(triangles)+' / '+str(PROFILE['triangle_budget'])+' 三角面'},
      {'id':'uv-presence','status':'pass' if not uv_missing else 'fail','message':str(uv_missing)+' 个图元缺少 UV0；不代表展开质量'},
      {'id':'texture-channels','status':'pass' if not missing else 'warn','message':'当前基线缺少：'+', '.join(sorted(set(missing))) if missing else '基线要求的贴图通道已绑定'},
      {'id':'texture-size','status':'warn' if any(not x['dimensions'] or max(x['dimensions'])>PROFILE['texture_edge_budget'] for x in images) else 'pass','message':'图像尺寸基线 '+str(PROFILE['texture_edge_budget'])},
      {'id':'artist-review','status':'unverified','message':'轮廓、拓扑流向、UV接缝、烘焙伪影和LOD切换需要人工或专门图像评测'}]
    return {'schema':'jarvis.studio3d.inspection.v1','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'profile':PROFILE,'triangles':triangles,'primitives':primitives,'materials':mats,'images':images,'textures':len(doc.get('textures',[])),'texture_memory_estimate_bytes':sum(x['rgba_mip_estimate_bytes'] or 0 for x in images),'extensions':doc.get('extensionsUsed',[]),'checks':checks,'AAA_certified':False}
