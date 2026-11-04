// Receipt-bound LOD pages use the existing allowed model.glb delivery route.
export function gameLodEntries(bundle,currentId,currentSha){
 if(!bundle)return [];
 if(bundle.schema!=='jarvis.game-lod-pages.v1'||!Array.isArray(bundle.levels)||bundle.levels.length!==4||!/^[a-f0-9]{64}$/.test(bundle.source_sha256))throw Error('游戏LOD清单无效');
 const levels=new Set(),jobs=new Set();
 for(const row of bundle.levels){
  if(!Number.isInteger(row.level)||row.level<0||row.level>3||levels.has(row.level)||!Number.isInteger(row.triangles)||row.triangles<1||row.triangles>1500000||!/^[a-f0-9]{32}$/.test(row.job_id)||jobs.has(row.job_id)||!/^[a-f0-9]{64}$/.test(row.sha256))throw Error('游戏LOD成员无效');
  levels.add(row.level);jobs.add(row.job_id);
 }
 const entries=[...bundle.levels].sort((a,b)=>a.level-b.level);
 if(bundle.high!==undefined){
  const high=bundle.high;
  if(!high||typeof high!=='object'||!Number.isInteger(high.triangles)||high.triangles<1||high.triangles>1500000||!/^[a-f0-9]{32}$/.test(high.job_id)||jobs.has(high.job_id)||!/^[a-f0-9]{64}$/.test(high.sha256))throw Error('原始高模成员无效');
  entries.unshift({...high,kind:'high'});
 }
 if(!entries.some(r=>r.job_id===currentId&&r.sha256===currentSha))throw Error('游戏LOD来源页不符');
 return entries;
}
export function gameLodLabel(row){return (row.kind==='high'?'原始高模':'LOD'+row.level)+' · '+row.triangles.toLocaleString()+' 三角面';}
