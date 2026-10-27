import {el,button,link,card,get,post,run,details,modal,icon,select,field} from './ui.js';
export const localModelsUiVersion='1.2.0';
const purposes=[
 {id:'llm',name:'聊天推理',icon:'chat',verb:'思考与回答',code:'REASON',description:'对话、写作、总结和任务规划。',guide:'把上下文组织成回答或计划。优先看回答质量、上下文长度和生成速度；能生成计划，不代表已获得执行工具的权限。',flow:['问题与上下文','理解与推理','回答或计划']},
 {id:'embedding',name:'记忆检索',icon:'memory',verb:'从资料中找线索',code:'RETRIEVE',description:'在记忆、文档和知识库里找相关内容。',guide:'把查询与资料编码成向量，用于语义检索。优先看多语言召回、向量维度和延迟；它本身不生成聊天回答。',flow:['问题与资料','语义向量','相关片段']},
 {id:'reranker',name:'检索重排',icon:'levels',verb:'把相关结果排在前面',code:'RERANK',description:'对召回结果再次比较，提升相关性。',guide:'先检索一批候选，再按问题重新排序。看排序质量与每批耗时；相关性打分不能证明内容真实。',flow:['问题与候选片段','逐项比较','重新排序']},
 {id:'stt',name:'语音识别',icon:'mic',verb:'听懂你说的话',code:'LISTEN',description:'把语音转成文字，支持语音输入。',guide:'重点看中文、英文和其他目标语言的识别错误率、噪声表现与实时率。识别文字和识别说话人是不同能力。',flow:['语音','识别语言与内容','文字']},
 {id:'tts',name:'语音合成',icon:'sound',verb:'用声音表达',code:'SPEAK',description:'把回复读出来，按模型支持控制音色和情绪。',guide:'先比较首音延迟、流畅度和自然度，再看语气、情绪与克隆能力。每个模型支持的功能不同，登记候选不代表已启用。',flow:['文字与表达要求','生成语音','声音']},
 {id:'speaker',name:'声纹识别',icon:'devices',verb:'区分是谁在说话',code:'IDENTIFY',description:'区分说话人，辅助识别用户。',guide:'重点看同一人匹配、不同人区分和噪声误识别。声纹、多人说话分段和重叠语音分离需分别验证；声纹不能单独代替高风险操作授权。',flow:['语音片段','说话人特征','身份候选']},
 {id:'vad',name:'语音检测',icon:'cpu',verb:'判断什么时候在说话',code:'DETECT',description:'检测开口和停顿，辅助录音与打断。',guide:'轻量检测人声的起止，帮助减少空白音频处理。看漏检、误触发和延迟；不负责听懂内容或确认身份。',flow:['连续音频','检测人声起止','有效语音段']},
 {id:'vision',name:'视觉理解',icon:'grid',verb:'理解图片与画面',code:'SEE',description:'理解图片、截图或其他视觉输入。',guide:'根据具体模型选择看图问答、文字识别或视觉编码。看图能力不等于拥有桌面控制权限，也不表示所有视觉任务都支持。',flow:['图片与问题','视觉分析','描述或特征']}
];
const otherPurpose={id:'other',name:'其他用途',icon:'grid',verb:'待补充用途说明',code:'EXTEND',description:'新登记类型需要独立说明与验证。',guide:'请先核对模型用途与运行适配。',flow:['输入','模型处理','输出']};
const purposeOf=m=>purposes.find(p=>p.id===m.kind)||otherPurpose;
const completeFiles=m=>m.files.length>0&&m.disk_bytes>=m.download_bytes;
const canStart=m=>m.adapter_ready&&completeFiles(m)&&!['failed','damaged'].includes(m.state);
const normalize=s=>String(s??'').normalize('NFKC').toLocaleLowerCase();
const languageLabel=m=>m.languages.map(x=>({zh:'中文',en:'英文',multilingual:'多语言'}[x]||x)).join(' / ');
const bytes=n=>n==null?'待测':n>=1073741824?(n/1073741824).toFixed(2)+' GiB':(n/1048576).toFixed(1)+' MiB';
const range=v=>!v?'待核验':bytes(v.low)===bytes(v.high)?bytes(v.low):bytes(v.low)+' – '+bytes(v.high);
const date=v=>v?new Date(v*1000).toLocaleString():'无';
const states={catalog:'未下载',ready:'文件已校验',downloading:'下载中',checking:'检查中',failed:'需要处理',interrupted:'已中断，可续传',damaged:'文件损坏'};
const jobs={download:'下载',repair:'修复',verify:'校验',start:'启动',standby:'待命',activate:'切换',rollback:'回退',embed:'检索测试',benchmark:'本机多语言评测',uninstall:'卸载',register:'登记',unselect:'取消默认',retire_previous:'解除旧模型保留'};
const outcomes={running:'进行中',succeeded:'完成',failed:'失败',cancelled:'已取消',interrupted:'已中断'};
function showBenchmark(title,b){
 const body=modal(title+' · 多语言检索评测');body.append(el('p',`固定合成样本 ${b.sample_count} 项 · ${date(b.completed_at)}。结果反映本评测集，失败项保留。`));
 const wrap=el('div',undefined,'lm-table-wrap'),table=el('table',undefined,'lm-table'),head=el('tr');
 for(const label of ['查询 / 语言','第一条检索结果','正确文档排名'])head.append(el('th',label));
 const thead=el('thead');thead.append(head);table.append(thead);const tbody=el('tbody');
 for(const c of b.cases){const tr=el('tr'),query=el('td');query.append(el('strong',c.query||c.id),el('p',c.language));const answer=el('td',c.top_text||c.top_document);if(c.rank!==1){tr.className='lm-miss';answer.append(el('p','预期：'+(c.expected_text||c.expected_document)));}tr.append(query,answer,el('td',c.rank===1?'1 · 命中':`${c.rank} · 首位未命中`));tbody.append(tr);}
 table.append(tbody);wrap.append(table);body.append(wrap);
}
function assessmentView(m){
 const a=m.assessment;if(!a)return el('p','服务更新后显示资源预测与评分。','note');
 const root=el('section',undefined,'lm-assessment');root.setAttribute('aria-label',m.title+' 资源与评价');
 const head=el('div',undefined,'lm-heading');head.append(el('strong',a.calibrated?'启动占用预测 · 本机实测已修正':'启动占用预测 · 尚未本机校准'),el('span','资料核验 '+(a.checked_at||'待补充'),'note'));root.append(head);
 const grid=el('div',undefined,'lm-resources');
 for(const [key,label] of [['disk','磁盘 · 模型文件'],['ram','RAM · 推理进程'],['vram','专用显存 · CPU 路径']]){
  const cell=el('div');cell.append(el('span',label,'note'),el('strong',range(a.expected[key])),el('small',key==='disk'?(a.expected[key]?.basis==='measured'?'已校验文件实测':m.files.length?'固定版本文件大小':'上游文件＋配置余量'):key==='ram'?(a.calibrated?'已测范围＋峰值 15% 余量':'工程估计 · 等待实测'):'CPU 不分配专用显存；GPU 路径待接入'));grid.append(cell);
 }root.append(grid,el('p',a.profile,'note'));
 if(a.calibrated){const v=a.measured;root.append(el('p',`已保留 ${v.samples} 次采样 · 最近 RAM ${bytes(v.rss_bytes)} · 已观测峰值 ${bytes(v.peak_rss_bytes)} · 最大已测 batch ${v.batch_observed_max??'未知'} / ${v.max_tokens_observed_max??'未知'} token · ${date(v.updated_at)}`,'note'));}
 root.append(el('p','预测只适用于注明的运行配置；长文本、大批量及 GPU 后端须另测。未启动时 RAM / 显存为 0；待命、重启和卸载文件不会清除校准记录。','note'));
 const scores=el('div',undefined,'lm-scores');
 for(const [key,label,hint] of [['resources','资源友好度',a.calibrated?'本机预测上界':'估计 RAM 上界'],['multilingual','语言覆盖',a.languages_count?`${a.languages_count}${a.languages_count>=100?'+':''} 种；覆盖不等于准确率`:'具体覆盖待核验'],['speed','本机速度',m.kind==='embedding'?'固定短查询 p50':'专用速度评测待接入'],['validation','验证覆盖','0 目录 / 1 文件 / 2 启动 / 3 回归 / 4 领域 / 5 跨机']]){
  const cell=el('div'),n=a.scores[key];cell.append(el('span',label),el('strong',n==null?'待测':n+' / 5'));
  if(n!=null){const meter=el('meter');meter.min=0;meter.max=5;meter.value=n;meter.setAttribute('aria-label',label+' '+n+' / 5');cell.append(meter);}cell.append(el('small',hint));scores.append(cell);
 }root.append(scores);
 const b=a.benchmark;
 if(a.stale_benchmark)root.append(el('p','评测集已更新，旧结果保留但不再计入当前评分。请重新运行本机评测。','note'));
 if(b){root.append(el('p',`本机检索命中 ${Math.round(b.hit_at_1*b.sample_count)}/${b.sample_count} · Hit@1 ${(b.hit_at_1*100).toFixed(1)}% · MRR ${b.mrr.toFixed(3)} · p50 ${b.latency_ms.p50.toFixed(1)} ms / p95 ${b.latency_ms.p95.toFixed(1)} ms`,'lm-result'),el('p','固定小样本多语言回归，包含易混淆候选；不等于通用准确率、事实核验能力或生产领域验收。','note'),button('查看每项评测结果',()=>showBenchmark(m.title,b)));}
 else root.append(el('p',m.kind==='embedding'?'本机检索质量：待测。文件 SHA-256 校验不等于检索准确度。':m.kind==='stt'?'语音质量待测：需按语言测 WER / CER 与实时率。':m.kind==='tts'?'语音质量待测：需测自然度、首音延迟、情绪和实时率。':'生成质量待测：需独立任务与事实核验评测。','note'));
 for(const o of a.official||[]){root.append(el('p',`官方参考 · ${o.metric}：${o.score} / 100 · ${o.precision}`,'note'));}
 const info=el('details');info.append(el('summary','评分依据、来源与适用范围'));
 info.append(el('p','资源友好度按 RAM 预测上界 ≤512 MiB / 1 / 2 / 4 GiB / 更高，评 5 / 4 / 3 / 2 / 1；语言覆盖按 ≥100 / 30 / 10 / 2 / 1 种计 5 / 4 / 3 / 2 / 1。速度按本机固定短查询 p50 ≤20 / 50 / 150 / 500 ms / 更慢计 5 / 4 / 3 / 2 / 1。不同类型不计算综合排名，缺测不记零分。'));
 info.append(el('p','磁盘不包含共享 Python 环境、索引或下载临时空间；RAM 为子进程 RSS。Apple 芯片统一内存不能将 RAM 与 GPU 数值简单相加；当前尚无 Mac/GPU 实测。预测不是资源上限保证。'));
 for(const note of a.notes||[])info.append(el('p',note));
 for(const s of a.sources||[]){const source=link(s.title,s.url);source.target='_blank';source.rel='noopener noreferrer';info.append(source,document.createTextNode(' · '));}
 if(a.other_contexts)info.append(el('p',`保留 ${a.other_contexts} 组旧设备 / 运行时记录；未用于当前配置的预测。`));
 root.append(info);return root;
}
export function localModelsView(body){
 if(!document.querySelector('link[data-local-models]')){const css=el('link');css.rel='stylesheet';css.href='/local-models.css';css.dataset.localModels='true';document.head.append(css);}
 body.classList.add('lm-center');body.dataset.localModelsUi=localModelsUiVersion;
 let stopped=false,timer=null,state=null,signature='',category='all',fetching=false;
 const expanded=new Set(),maintenanceOpen=new Set();
 const overview=el('section',undefined,'lm-overview');overview.setAttribute('aria-label','本地模型用途导航');
 const overviewHead=el('div',undefined,'lm-overview-head'),all=button('全部用途',()=>choose('all'),'lm-all');
 const title=el('div');title.append(el('span','CAPABILITY DIRECTORY','eyebrow'),el('h2','先选用途，再选模型'),el('p','每种模型各有所长。按需要挑选，安装与运行状态单独确认。','note'));
 const totals=el('div',undefined,'lm-totals');overviewHead.append(title,all);overview.append(overviewHead,totals);
 const categories=el('div',undefined,'lm-categories');overview.append(categories);
 const categoryNodes=new Map();
 function addCategory(p){
  const b=button('',()=>choose(p.id),'lm-category'),top=el('span',undefined,'lm-category-top'),glyph=el('span',undefined,'lm-category-glyph'),count=el('span','','lm-category-count');glyph.append(icon(p.icon));top.append(glyph,el('span',p.code,'lm-category-code'),count);
  b.append(top,el('strong',p.name),el('span',p.description,'lm-category-description'));b.setAttribute('aria-controls','local-model-results');categories.append(b);categoryNodes.set(p.id,{button:b,count});
 }
 purposes.forEach(addCategory);
 const guide=el('section',undefined,'lm-purpose-guide');guide.setAttribute('aria-label','用途与选择建议');
 const search=el('input');search.type='search';search.placeholder='搜索模型名称、语言或用途…';search.setAttribute('aria-label','搜索本地模型');
 const availability=select([['all','全部状态'],['installed','已下载'],['ready','可启动'],['running','运行中'],['pending','待准备']]);availability.setAttribute('aria-label','本地模型状态');
 const ordering=select([['available','已安装优先'],['ram','预计 RAM 从小到大'],['name','模型名称']]);ordering.setAttribute('aria-label','本地模型排序');
 const reset=button('清除筛选',()=>{search.value='';availability.value='all';ordering.value='available';category='all';render();});
 const filters=el('div',undefined,'lm-filters');filters.append(field('搜索模型',search),field('运行状态',availability),field('排序方式',ordering),reset);
 const resultCount=el('p','','note');resultCount.setAttribute('role','status');resultCount.setAttribute('aria-live','polite');
 const status=el('p','','note'),controls=el('div',undefined,'row'),list=el('div');list.id='local-model-results';
 const manager=el('details',undefined,'lm-manager');manager.append(el('summary','管理与恢复'),controls);
 body.append(overview,guide,filters,resultCount,status,manager,list);
 const act=async(action,id,extra={})=>{if(!state)return;await post('/api/local-models',{action,revision:state.revision,...(id?{id}:{}),...extra});await draw();};
 function choose(id){category=id;render();}
 search.addEventListener('input',()=>render());availability.addEventListener('change',()=>render());ordering.addEventListener('change',()=>render());
 function rememberDisclosure(node,id,set){node.open=set.has(id);node.addEventListener('toggle',()=>{if(node.isConnected){if(node.open)set.add(id);else set.delete(id);}});}
 function drawModel(m,busy){
  const p=purposeOf(m),c=el('article',undefined,'card lm-model');c.dataset.modelId=m.id;c.setAttribute('aria-label',m.title);
  const head=el('div',undefined,'lm-model-heading'),name=el('div');name.append(el('h3',m.title),el('p',`${p.name} · ${languageLabel(m)}${m.dimension?' · '+m.dimension+' 维':''}`,'note'));
  const badges=el('div',undefined,'lm-badges');
  if(m.selected)badges.append(el('span','当前默认','lm-badge selected'));
  const statusLabel=m.loaded?'运行中':canStart(m)?'可启动':m.disk_bytes?'文件待检查':m.files.length?'可下载':'参考候选';
  badges.append(el('span',statusLabel,'lm-badge'+(m.loaded?' running':'')));head.append(name,badges);c.append(head);
  const a=m.assessment,resourceLine=el('div',undefined,'lm-compact-resources');
  for(const [k,label] of [['disk','预计磁盘'],['ram','启动 RAM'],['vram','专用显存 · CPU']]){const unit=el('div');unit.append(el('span',label),el('strong',range(a?.expected?.[k])));resourceLine.append(unit);}c.append(resourceLine);
  const currentState=m.loaded?'推理进程运行中':m.state==='catalog'&&m.disk_bytes?'发现文件，启动前需校验':states[m.state]||m.state;
  c.append(el('p',`${currentState} · 当前磁盘 ${bytes(m.disk_bytes)} · 当前 RAM ${bytes(m.memory?.rss_bytes)} · 当前专用显存 ${bytes(m.memory?.gpu_bytes)}${m.partial_bytes?' · 下载暂存 '+bytes(m.partial_bytes):''} · ${a?.calibrated?'预测已由本机实测修正':'预测尚未本机校准'}`,'note'));
  if(a){
   const scores=el('div',undefined,'lm-compact-scores');
   for(const [key,label] of [['resources','资源友好'],['multilingual','语言覆盖'],['speed','本机速度'],['validation','验证覆盖']])scores.append(el('span',label+' '+(a.scores[key]==null?'待测':a.scores[key]+'/5')));
   c.append(scores);
   if(a.benchmark)c.append(el('p',`检索回归 ${Math.round(a.benchmark.hit_at_1*a.benchmark.sample_count)}/${a.benchmark.sample_count} 命中 · 短查询 p50 ${a.benchmark.latency_ms.p50.toFixed(1)} ms · 限本评测集`,'lm-quality-line'));
   else c.append(el('p',m.kind==='embedding'?'本机检索效果待测；语言覆盖分不代表准确率。':m.kind==='tts'?'自然度、首音延迟与情绪表达待测。':m.kind==='stt'?'各语言识别错误率与实时率待测。':'本机任务效果待测。','note'));
  }
  if(m.error)c.append(el('p','需要处理：'+m.error,'danger'));
  const actions=el('div',undefined,'lm-model-actions');
  const expand=el('details',undefined,'lm-details');rememberDisclosure(expand,m.id,expanded);expand.append(el('summary','资源明细与评分依据'),assessmentView(m));
  const mainAction=m.loaded?'standby':m.files.length&&['failed','damaged'].includes(m.state)?'repair':completeFiles(m)&&m.adapter_ready?'start':m.files.length&&!completeFiles(m)?'download':null;
  if(mainAction){const b=button({standby:'待命 · 释放内存',start:'启动模型',download:'下载 / 续传',repair:'检查并修复文件'}[mainAction],()=>act(mainAction,m.id),'lm-primary');b.disabled=busy;actions.append(b);}
  else actions.append(el('span','运行适配待接入','note'));
  if(m.adapter_ready&&completeFiles(m)){const b=button('本机评测',()=>act('benchmark',m.id));b.disabled=busy;actions.append(b);}
  if(a?.benchmark)actions.append(button('查看评测结果',()=>showBenchmark(m.title,a.benchmark)));
  const source=link('官方模型页 ↗',m.source);source.target='_blank';source.rel='noopener noreferrer';actions.append(source);c.append(actions,expand);
  const maintenance=el('details',undefined,'lm-maintenance');rememberDisclosure(maintenance,m.id,maintenanceOpen);maintenance.append(el('summary','文件维护与版本管理'));
  maintenance.append(el('p',`${m.files.length?'完整文件 '+bytes(m.download_bytes):'下载配方待核验'} · ${m.adapter_ready?'运行适配已接入':'运行适配待接入'} · ${m.license}${m.dimension?' · 支持维度 '+m.dimensions.join('/') :''}`,'note'));
  const row=el('div',undefined,'row');row.append(button('清单 / 修订 / 向量空间',()=>details(m.title,m)));
  for(const [action,label] of [['download','下载 / 续传'],['verify','校验文件'],['repair','修复文件'],['start','启动'],['standby','待命'],['activate','设为默认 / 更换'],['uninstall','卸载文件']]){
   const b=button(label,()=>act(action,m.id));b.disabled=busy||!m.files.length||(['start','activate'].includes(action)&&(!m.adapter_ready||!completeFiles(m)))||(action==='standby'&&!m.loaded)||(['repair','uninstall'].includes(action)&&m.loaded);row.append(b);
  }maintenance.append(row);c.append(maintenance);return c;
 }
 function render(){
  if(!state||stopped)return;
  if(state.manager.status==='unavailable'){status.textContent='本地模型管理器暂不可用：'+state.manager.error+'。其余工作台继续运行。';list.replaceChildren();controls.replaceChildren();return;}
  const models=state.models,job=state.job,busy=job?.status==='running';
  totals.replaceChildren();for(const [label,n] of [['目录模型',models.length],['已下载',models.filter(completeFiles).length],['可启动',models.filter(canStart).length],['运行中',models.filter(m=>m.loaded).length]]){const item=el('span');item.append(el('strong',String(n)),document.createTextNode(label));totals.append(item);}
  if(models.some(m=>purposeOf(m).id==='other')&&!categoryNodes.has('other'))addCategory(otherPurpose);
  all.textContent=`全部用途 · ${models.length}`;all.setAttribute('aria-pressed',String(category==='all'));
  for(const [id,nodes] of categoryNodes){const subset=models.filter(m=>purposeOf(m).id===id),ready=subset.filter(canStart).length;nodes.count.textContent=subset.length?subset.length+' 个':'待接入';nodes.button.setAttribute('aria-pressed',String(id===category));nodes.button.setAttribute('aria-label',`${(purposes.find(p=>p.id===id)||otherPurpose).name}，${subset.length} 个模型${ready?'，'+ready+' 个可启动':''}`);}
  const p=purposes.find(p=>p.id===category)||(category==='other'?otherPurpose:null);guide.replaceChildren();
  if(p){const copy=el('div');copy.append(el('span',p.code,'eyebrow'),el('h3',p.verb),el('p',p.guide,'note'));const flow=el('ol',undefined,'lm-flow');for(const step of p.flow)flow.append(el('li',step));guide.append(copy,flow);}
  else guide.append(el('p','按用途分组展示。先找到需要的能力，再比较同类模型；模型已下载、能启动和效果已验证是不同状态。','note'));
  if(category==='embedding')guide.append(el('p','E5 INT8 是已接通的轻量基线；EmbeddingGemma 与 Qwen3 的候选版本需在同一环境对测。语言覆盖、资源和速度分不等于综合效果排名。','lm-choice-note'));
  status.textContent=job?`${jobs[job.action]||job.action||'上次操作'} · ${outcomes[job.status]||job.status}${job.model?' · '+(models.find(m=>m.id===job.model)?.title||job.model):''}${job.error?' · '+job.error:''}${job.downloaded_bytes?' · '+bytes(job.downloaded_bytes):''}`:'后台待命 · 选择分类不会启动或下载模型';
  controls.replaceChildren(button('取消当前操作',()=>act('cancel')),button('回退上一模型',()=>act('rollback')),button('取消默认并释放内存',()=>act('unselect')),button('解除旧模型保留',()=>act('retire_previous')),button('管理器自身说明',()=>details('本地模型底座',{ui_version:localModelsUiVersion,...state.manager,runtime:state.runtime})));
  controls.append(el('p',`默认：${state.selected||'未选择'} · 回退保留：${state.previous||'无'}。资源为最近推理采样；后台操作在切换分类后继续显示。`,'note'));
  const bs=controls.querySelectorAll('button');bs[0].disabled=!busy;bs[1].disabled=busy||!state.previous;bs[2].disabled=busy||!state.selected;bs[3].disabled=busy||!state.previous;
  if(busy)manager.open=true;
  const term=normalize(search.value).trim();
  const visible=models.filter(m=>{
   const purpose=purposeOf(m),text=normalize([m.id,m.title,m.kind,...m.languages,languageLabel(m),purpose.name,purpose.description,purpose.verb,m.dimension||'',...m.dimensions].join(' '));
   return (category==='all'||purpose.id===category)&&(!term||text.includes(term))&&({all:true,installed:completeFiles(m),ready:canStart(m),running:m.loaded,pending:!canStart(m)}[availability.value]);
  });
  const priority=m=>(m.selected?1000:0)+(m.loaded?500:0)+(m.disk_bytes?100:0)+(m.adapter_ready?50:0);
  visible.sort((a,b)=>ordering.value==='ram'?(a.assessment?.expected?.ram?.high??Infinity)-(b.assessment?.expected?.ram?.high??Infinity):ordering.value==='name'?a.title.localeCompare(b.title,'zh'):priority(b)-priority(a)||a.title.localeCompare(b.title,'zh'));
  resultCount.textContent=`${p?.name||'全部用途'} · 显示 ${visible.length} / ${models.filter(m=>category==='all'||purposeOf(m).id===category).length} 个模型${term?' · 搜索「'+search.value+'」':''}${availability.value!=='all'?' · '+availability.selectedOptions[0].textContent:''}`;
  reset.disabled=category==='all'&&!search.value&&availability.value==='all'&&ordering.value==='available';list.replaceChildren();
  if(!visible.length){const empty=card(models.some(m=>category==='all'||purposeOf(m).id===category)?'没有符合筛选条件的模型':'这类模型尚未登记',models.some(m=>category==='all'||purposeOf(m).id===category)?'可以清除搜索或状态条件，再查看该用途的其他模型。':'用途入口已经准备好；接入经过核验的模型及适配器后，会在这里显示。选择这个分类不会下载或启动模型。');empty.classList.add('lm-empty');empty.append(button('查看全部模型',()=>{category='all';search.value='';availability.value='all';render();}));list.append(empty);}
  for(const purpose of [...purposes,otherPurpose]){const items=visible.filter(m=>purposeOf(m).id===purpose.id);if(!items.length)continue;const group=el('section',undefined,'lm-group');group.setAttribute('aria-label',purpose.name+'模型');const heading=el('div',undefined,'lm-group-heading');heading.append(icon(purpose.icon),el('h3',purpose.name),el('span',items.length+' 个','badge'),el('span',purpose.description,'note'));group.append(heading);for(const m of items)group.append(drawModel(m,busy));list.append(group);}
  test.hidden=!(['all','embedding'].includes(category));embedButton.disabled=busy||!models.some(m=>m.loaded&&m.kind==='embedding');
 }
 async function draw(){
  if(fetching||stopped)return;fetching=true;
  try{const next=await get('/api/local-models');if(stopped)return;state=next;const current=JSON.stringify({...next,observed_at:undefined});if(current!==signature){signature=current;render();}}
  finally{fetching=false;}
 }
 const test=el('details',undefined,'lm-test'),output=el('div');test.append(el('summary','高级 · 本地向量测试'),el('p','启动向量模型后可测试短文本；只调用本机编码器，输入和向量不写入管理日志。','note'));
 const input=el('textarea');input.value='我喜欢茶\nI like tea\n汽车发动机';input.rows=4;input.setAttribute('aria-label','逐行输入多语言测试文本');
 const embedButton=button('生成 passage 向量',async()=>{await act('embed',null,{texts:input.value.split('\n').filter(Boolean),role:'passage'});await pollResult();});embedButton.disabled=true;test.append(input,embedButton,output);
 async function pollResult(){for(let i=0;i<80&&!stopped;i++){await new Promise(r=>setTimeout(r,500));const r=await get('/api/local-models/result');if(stopped)return;if(r){output.replaceChildren(el('pre',JSON.stringify(r.result?.vectors?r.result.vectors.map(v=>({dimension:v.length,first_values:v.slice(0,5)})):r,null,2)));break;}}}
 const register=el('details',undefined,'lm-register'),manifest=el('textarea');manifest.rows=8;manifest.setAttribute('aria-label','模型清单 JSON');register.append(el('summary','高级 · 登记新版本或其他模型'),el('p','类型决定用途分类。新修订使用新 ID；登记只保存清单，无对应运行适配器时不会变为可用。','note'),manifest,button('登记清单',()=>act('register',null,{manifest:JSON.parse(manifest.value)})));body.append(test,register);
 run(draw);timer=setInterval(()=>run(draw),2000);return()=>{stopped=true;clearInterval(timer);};
}
