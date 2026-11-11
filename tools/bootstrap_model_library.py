"""Enroll the actual current WWII models and their reusable component files."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT)]
from modules.skills.model_library.store import Library,digest

def main():
 record=json.loads((ROOT/'user-data/model-library-preparation.json').read_text());assert record['status']=='SUCCEEDED';prep=Path(record['folder'])
 report=json.loads((prep/'report.json').read_text());assert report['sources_unchanged']
 with Library(ROOT/'user-data') as lib:
  out=lib.root
  if (out/'bootstrap-report.json').exists():raise RuntimeError('Initial enrolment already completed; use explicit registration and preserve edited metadata.')
  def asset(ident,name,kind,description,status='reference',tags=(),default='original',parent=None):
   lib.put_asset({'id':ident,'name':name,'category':'wwii','kind':kind,'description':description,'status':status,'tags':['二战','德军',*tags],'default_variant':default,'parent_asset_id':parent,'usage':'展示、游戏制作参考；明确标注的游戏LOD可作为游戏版本导入','rights':'用户项目资产；原始参考与第三方分件来源保留在来源文件中'})
  def file(ident,path,role,sha=None):return lib.add_file(ident,Path(path),role,sha)
  def variant(ident,key,path,label,role='high',sha=None):
   f=file(ident,path,role,sha);lib.add_variant(ident,key,f,label,role);return f
  def case(ident,name,title,summary,pre,neg,source):
   proof=file(ident,source,'method-evidence');lib.add_case(ident,{'id':name,'title':title,'summary':summary,'prerequisites':pre,'counterexamples':neg,'scope':'本资产记录；需重新验证适用条件','evidence_file_id':proof,'evidence_sha256':digest(source)})
  # The current PaK38 comes from current-model, never the stale root high files.
  pak=ROOT/'3DModels/PaK38';c=json.loads((pak/'metadata/current-model.json').read_text());w=c['working_candidate'];game=json.loads((pak/'game/PaK38_LOD_v2/manifest.json').read_text())
  asset('pak38','PaK 38 · 50毫米反坦克炮','model','已确认高模，关联四档纯三角形游戏LOD及编辑源。','accepted',['火炮','反坦克炮','LOD','游戏'],default='lod0')
  variant('pak38','original',pak/w['model'],'原始高模 · 575,538 三角面','high',w['model_sha256']);file('pak38',pak/w['editable_blend'],'editable',w['editable_blend_sha256']);file('pak38',pak/w['blend'],'mapped-source',w['blend_sha256'])
  for row in game['levels']:
   variant('pak38','lod'+str(row['level']),pak/row['model'],'LOD'+str(row['level'])+' · '+format(row['triangles'],',')+' 三角面','game',row['model_sha256']);file('pak38',pak/row['blend'],'game-blend',row['blend_sha256'])
  file('pak38',pak/'game/PaK38_LOD_v2/PaK38_Game_LOD0-3.zip','game-package');file('pak38',pak/'metadata/demonstrations/paint-feature-tool-02-jarvis/after/preview.png','cover')
  for view in ['front','rear','left','right','top']:
   p=ROOT/'user-data/artifacts/studio3d'/w['viewer_job_id']/('view-'+view+'.png')
   if p.exists():file('pak38',p,'view-'+view)
  case('pak38','lod-component-preservation','从高模到可辨识的游戏LOD','按主体保留低模预算；用实际回读图检查主梁、轮胎与轮廓，低预算时删除小附件。',['用户已确认高模及预算','有明确的语义主体和原点','实际导出、三角数与图像检查'],['2995面版本虽格式通过却丢失主梁，已拒收','轮廓LOD不能当近景高模或碰撞认证'],pak/'game/PaK38_LOD_v2/evidence/local-method-candidate.json')
  # leFH18 user approval and exact final hashes are authoritative.
  le=ROOT/'3DModels/leFH18';a=json.loads((le/'metadata/user-acceptance.json').read_text());asset('lefh18','leFH 18 · 105毫米榴弹炮','model','已验收的高模母版，保留编辑源、PBR贴图与外观动画。','accepted',['火炮','榴弹炮','高模','材质'])
  variant('lefh18','original',le/'leFH18-high.glb','已验收高模 · 701,654 三角面','high',a['files']['leFH18-high.glb']['sha256']);file('lefh18',le/'leFH18-editable.blend','editable',a['files']['leFH18-editable.blend']['sha256']);file('lefh18',le/'leFH18-high.blend','mapped-source',a['files']['leFH18-high.blend']['sha256']);file('lefh18',le/'metadata/evidence/browser/hero.png','cover')
  for p in (le/'textures').glob('*'):
   if p.is_file() and p.suffix.lower() in {'.png','.jpg'}:file('lefh18',p,'texture')
  file('lefh18',le/'metadata/user-acceptance.json','provenance');file('lefh18',le/'metadata/optimization-recipe.json','method-evidence')
  case('lefh18','approved-finish-reference','用已验收成品核对材质和整体质量','保留漆面、金属、橡胶与做旧效果的真实成品作为视觉对照。它提供本资产实例，不是可直接迁移的通用着色器配方。',['同类外观目标','核对实际材质和灯光','保留参考源摘要'],['光照差异不能直接当成漆色差异','不复制专用UV或属性数值到不同形状'],le/'metadata/optimization-recipe.json')
  tank=ROOT/'3DModels/PanzerII-reference-assembly';r=tank/'revision-r3';native=json.loads((r/'metadata/native-receipt.json').read_text());asset('panzer-ii','二号坦克 · r3 装配参考','model','采用改造后的炮塔与已贴合车灯；轻量展示版和原始装配高模分别保留。',tags=['坦克','载具','装配','炮塔'],default='display')
  variant('panzer-ii','display',prep/'tank-display.glb','轻量展示预览 · 非游戏LOD','preview');variant('panzer-ii','original',r/'assembled.glb','r3 原始装配高模 · 下载参考','high',native['outputs']['assembled.glb']['sha256']);file('panzer-ii',r/'assembled.blend','editable',native['outputs']['assembled.blend']['sha256']);file('panzer-ii',prep/'tank-display.png','cover');file('panzer-ii',r/'metadata/visual-review.json','provenance')
  for name in ['front','rear','left','right','top']:
   p=r/'renders'/(name+'.png')
   if p.exists():file('panzer-ii',p,'view-'+name)
  methods=json.loads((r/'metadata/local-methods.json').read_text())
  for m in methods['cases'][:3]:case('panzer-ii',m['id'],m['title'],m['summary'],[k+' = '+str(v) for k,v in m.get('requires',{}).items()],[m['counterexamples']],r/'metadata/local-methods.json')
  names={'hull':'车体','turret':'炮塔 · r3改造','gun':'主炮','mantlet':'炮盾','track_left':'左履带与轮组','headlamp':'车灯 · 贴合修正版'}
  for key,title in names.items():
   ident='panzer-'+key.replace('_','-');asset(ident,'二号坦克 · '+title,'part','从r3装配源提取，保留原安装坐标；可作为后续装配参考。',tags=['坦克','部件',title],default='display',parent='panzer-ii');variant(ident,'display',prep/('tank-'+key+'.glb'),'展示预览','preview');variant(ident,'original',prep/('tank-'+key+'-original.glb'),'原始部件 · 保留原安装变换','high');file(ident,prep/('tank-'+key+'.png'),'cover')
  for key,title in [('wheel-left','左轮总成'),('shield','炮盾总成'),('barrel','炮管总成'),('trail-left','左炮架与驻锄')]:
   ident='pak38-'+key;asset(ident,'PaK 38 · '+title,'part','从已确认的当前高模提取，几何、贴图及原安装变换保留。',tags=['火炮','部件',title],parent='pak38');variant(ident,'original',prep/('pak-'+key+'.glb'),'当前高模部件','high');file(ident,prep/('pak-'+key+'.png'),'cover')
  result=lib.catalogue();summary={'assets':len(result['assets']),'complete_models':sum(a['kind']=='model' for a in result['assets']),'parts':sum(a['kind']=='part' for a in result['assets']),'preparation':str(prep),'storage':str(lib.root),'new_model_calls':0,'source_files_unchanged':True};(out/'bootstrap-report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
