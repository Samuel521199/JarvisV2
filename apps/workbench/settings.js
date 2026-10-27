import {workStatusView} from './work-status.js';
import {mailboxView} from './mailbox.js';
import {$,el,icon,iconButton,button,link,input,select,field,get,post,run,notice,modal,details,initModal,card,applyPreferences,savePreferences,states,levels,download} from './ui.js';
import {cinema,setSound,unlockSound,soundState,brandState} from './brand.js';
import {extensionsView} from './settings-extensions.js';
import {resources,networkView,runtimeView} from './settings-runtime.js';
import {ModelSettings,usageView} from './settings-models.js';
import {memoryView} from './memory.js';
import {developmentView} from './development.js';
import {studio3d} from './settings-studio3d.js';
import {anatomyStudio} from './settings-anatomy.js';
import {toolsView} from './tools.js';
import {goalsView} from './goals.js';
const modelManager=new ModelSettings(()=>snapshot.settings,value=>{snapshot.settings=value;route();});
let snapshot,skills=[],usage=[],tab='home',cleanup=()=>{};
async function refresh(){[snapshot,skills,usage]=await Promise.all([get('/api/snapshot'),get('/api/skills'),get('/api/usage')]);applyPreferences(snapshot.settings.ui);syncAppearance();route();}
const pages={mail:['mail','Gmail 邮件助手','连接与重连、阅读、分类、草稿和经过审阅的邮箱操作。'],'local-models':['cpu','本地模型','下载、启动、待命、修复与版本更换。'],home:['home','设置总览','偏好与后台管理，集中在一个地方。'],appearance:['star','外观','配色、动画与阅读体验。'],memory:['memory','记忆与知识','可纠正的个人背景、项目资料与候选记忆。'],plans:['calendar','目标与计划','从目标到可修改计划，再到执行和交付。'],skill:['star','技能与工具','按任务选用合适的技能，集中管理使用条件。'],devices:['devices','设备与共享','设备能力与分域共享。'],private:['lock','人员与私密资料','个人、家庭与小团体的独立资料边界。'],network:['network','网络与离线','查看模型通道与离线准备状态。'],coding:['code','编码协作','候选、独立检查与外部 Codex。'],growth:['cpu','成长中心','自检、自愈与进化各司其职。'],modules:['grid','模块与升级','独立能力、运行状态与发布恢复记录。'],overview:['levels','用量总览','用真实调用回执了解模型消耗。'],connections:['network','接入方与 Key','模型供应商、凭据状态与连接记录。'],models:['levels','模型与价格','默认模型、推理级别与备选顺序。'],calls:['file','调用明细','逐次查看本机保存的调用回执。'],tasks:['tools','后台任务','任务、研发过程与执行记录。']};
// A single navigation registry preserves every existing hash and business view.
const domains=[
 {id:'interface',title:'外观与交互',code:'INTERFACE',icon:'star',pages:['appearance'],note:'主题、声音与品牌动效'},
 {id:'cognition',title:'思考与成长',code:'COGNITION',icon:'memory',pages:['memory','plans','growth'],note:'记忆、目标与成长路径'},
 {id:'inference',title:'模型与费用',code:'INFERENCE',icon:'network',pages:['connections','models','local-models','overview','calls'],note:'模型连接、路由与每笔消耗'},
 {id:'execution',title:'技能与执行',code:'EXECUTION',icon:'tools',pages:['skill','coding','tasks'],note:'工具协作、研发与后台任务'},
 {id:'connection',title:'设备与连接',code:'CONNECTION',icon:'devices',pages:['devices','network','mail'],note:'设备互联与离线准备'},
 {id:'system',title:'系统与资料',code:'SYSTEM',icon:'grid',pages:['modules','private'],note:'模块维护与个人资料边界'}
];
const themes=[['dark','深空冷蓝'],['light','明亮'],['warm','暖砂'],['mist','雾蓝'],['forest','森林'],['midnight','午夜'],['system','跟随系统']];
// Each destination owns its symbol and illustration. These show the purpose of
// the page, never fabricated telemetry or completion of a real operation.
const sectionDesigns={
 mail:{code:'MAIL ASSISTANT',title:'读懂来信，核对每一次行动',steps:['连接邮箱','阅读与分类','审阅与恢复'],symbol:'M3 5h18v14H3zM3 6l9 7 9-7',art:'<path class="faint" d="M34 26h182v84H34zM34 29l91 61 91-61"/><path class="accent" d="M49 98l53-38M201 98l-53-38"/><circle class="accent" cx="206" cy="27" r="11"/>'},
 appearance:{code:'VISUAL LAB',title:'为你的工作空间校准每一处细节',steps:['选择配色','调整反馈','即时预览'],symbol:'M4 4h16v16H4zM4 10h16M10 10v10M7 7h.1M14 14h3M14 17h3',art:'<g class="prism-back"><path d="M66 92V38l60-20 56 20v54l-56 20Z"/><path d="m66 38 60 20 56-20M126 58v54"/></g><g class="accent fx"><path d="m88 29 60 21v54M108 22l60 22v54"/><path d="m66 59 60 20 56-20"/></g><path class="faint" d="M30 105h44M178 26h36M36 101v8M208 22v8"/>'},
 memory:{code:'MEMORY ARCHIVE',title:'留下有用的记忆，保持清晰的边界',steps:['分域整理','核对来源','随时纠正'],symbol:'M4 7 12 3l8 4-8 4ZM4 12l8 4 8-4M4 17l8 4 8-4',art:'<path class="faint" d="M35 30v78h180M42 24v8M32 105h6"/><g class="archive-back"><path d="m65 57 62-30 65 30-65 30Z"/><path d="m65 72 62 30 65-30"/><path d="m65 87 62 30 65-30"/></g><path class="accent" d="m65 42 62-30 65 30-65 30Z"/><circle class="accent fill fx" cx="127" cy="42" r="4"/><path d="M112 42h-17M159 42h-17"/>'},
 plans:{code:'MISSION PATH',title:'把目标拆成可以核对的下一步',steps:['描述目标','核对计划','执行与交付'],symbol:'M3 6h5v5H3zM16 13h5v5h-5zM8 8h10v5M6 11v7h10',art:'<path class="faint" d="M26 102h203M26 25v77"/><path class="accent fx" d="M40 85h42V59h66V31h62"/><g><rect x="33" y="78" width="14" height="14"/><rect x="75" y="52" width="14" height="14"/><rect x="141" y="24" width="14" height="14"/><path d="M201 24h18v14h-18zM207 20v-7h20l-6 5 6 5h-20"/></g>'},
 growth:{code:'EVOLUTION LAB',title:'让每一次改进，都留下可验证的结果',steps:['自检','恢复接续','候选进化'],symbol:'M12 21V11M12 15 5 8M12 11l7-7M3 4h5v5H3zM17 2h5v5h-5zM10 7V3',art:'<path class="faint" d="M38 111h176M126 112V20"/><g class="growth-tree fx"><path d="M126 107V67l-46-22M126 80l49-26M126 59V38l-21-20M126 44l29-24"/><circle class="accent" cx="80" cy="45" r="9"/><circle class="accent" cx="175" cy="54" r="11"/><path class="accent" d="M98 11h14v14H98zM149 12h14v14h-14z"/><path d="M126 91h-22M137 65h20"/></g>'},
 connections:{code:'PROVIDER SWITCHBOARD',title:'每条模型通道，独立连接与管理',steps:['接入方式','凭据配置','默认路由'],symbol:'M7 3v5M17 3v5M4 8h6v6H4zM14 8h6v6h-6zM7 14v5h10v-5M12 19v3',art:'<path d="M25 24h44v22H25zM25 84h44v22H25zM183 54h44v22h-44zM106 49h35v32h-35z"/><path class="accent fx" d="M69 35h17l20 25M69 95h17l20-25M141 65h42"/><path class="faint" d="M35 32h12M35 39h23M35 92h12M35 99h23M194 65h22M113 56v18M133 56v18"/>'},
 models:{code:'MODEL MATRIX',title:'能力、推理档位与价格，在此对齐',steps:['模型目录','默认选择','价格核对'],symbol:'M4 3h6v7H4zM14 3h6v7h-6zM4 14h6v7H4zM14 14h6v7h-6zM10 6h4M10 17h4',art:'<g class="model-blades fx"><path d="m61 27 30-10v94l-30-10Z"/><path d="m108 27 30-10v94l-30-10Z"/><path d="m155 27 30-10v94l-30-10Z"/></g><path class="accent" d="M70 42h12M117 42h12M164 42h12M70 54h12M117 54h12M164 54h12"/><path class="faint" d="M39 116h167M91 64h17M138 64h17"/>'},
 'local-models':{code:'LOCAL COMPUTE',title:'在本机准备模型，按需分配算力',steps:['文件准备','运行管理','质量另验'],symbol:'M6 6h12v12H6zM9 9h6v6H9zM9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M18 9h4M2 15h4M18 15h4',art:'<path class="faint" d="m42 82 84-40 84 40-84 40ZM42 82v8l84 40 84-40v-8"/><g class="compute-stack fx"><path d="m62 57 64-31 64 31-64 31ZM62 57v19l64 31 64-31V57"/><path class="accent" d="m94 55 32-15 32 15-32 15ZM126 88v19"/><path d="M76 70v9M91 77v9M106 84v9M146 84v9M161 77v9M176 70v9"/></g>'},
 overview:{code:'USAGE OBSERVATORY',title:'从真实回执，看清每一笔消耗',steps:['时间范围','模型与渠道','费用核对'],symbol:'M3 3v18h18M7 16v-4M12 16V6M17 16v-7',art:'<path class="faint" d="M35 23v83h184M35 80h184M35 54h184M35 28h184"/><g class="cost-bars fx"><path d="M57 104V76h17v28M91 104V58h17v46M125 104V71h17v33M159 104V42h17v62"/></g><path class="accent" d="m52 65 46-23 37 11 50-33M175 20h10v10"/>'},
 calls:{code:'CALL LEDGER',title:'一条调用，一份可追溯的记录',steps:['筛选记录','查看快照','导出明细'],symbol:'M5 3h14v18H5zM8 7h2M13 7h3M8 12h2M13 12h3M8 17h2M13 17h3',art:'<path d="M67 12h99l22 22v81H67ZM166 12v22h22"/><path d="M82 43h12M107 43h62M82 62h12M107 62h62M82 81h12M107 81h62M82 100h12M107 100h43"/><path class="accent ledger-scan fx" d="M56 43h142M56 39v8M198 39v8"/>'},
 skill:{code:'CAPABILITY LIBRARY',title:'按任务找到方法，而不是堆叠工具',steps:['选择技能','检查条件','按需使用'],symbol:'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM17 13v8M13 17h8',art:'<g class="skill-tiles fx"><path d="M49 24h39v35H49zM106 24h39v35h-39zM163 24h39v35h-39zM49 77h39v35H49zM106 77h39v35h-39z"/><path class="accent" d="M180 76v36M163 94h36M60 37h17M60 45h11M117 37h17M117 45h11M174 37h17M174 45h11"/></g><path class="faint" d="M88 42h18M145 42h18M68 59v18M125 59v18"/>'},
 tools:{code:'TOOL BENCH',title:'调用已发布能力，把结果留在本机',steps:['选择工具','填写输入','核对产物'],symbol:'M4 5h8v5H4zM12 7h8v5M20 12h-8v7h8zM4 10v9h8',art:'<path d="M34 101h184M49 101V85h39v16M102 101V65h39v36M155 101V45h39v56"/><path class="accent tool-arm fx" d="M66 42h58V25h49M66 42v26M58 68v10h16V68"/><circle cx="124" cy="42" r="6"/><path class="faint" d="M40 112h168"/>'},
 mcp:{code:'CONNECTOR BRIDGE',title:'连接外部工具，明确每次调用边界',steps:['登记端点','检查工具','选择启用'],symbol:'M2 8h6v8H2zM16 8h6v8h-6zM8 10h8M8 14h8M4 5v3M20 16v3',art:'<path d="M30 43h52v44H30zM170 43h52v44h-52zM82 52h23v26H82M147 52h23v26h-23"/><path class="accent bridge-line fx" d="M105 58h42M105 72h42"/><path d="M41 54h12v22H41M199 54h12v22h-12M51 30v13M201 87v13"/><path class="faint" d="M109 42h34M109 88h34"/>'},
 coding:{code:'BUILD STUDIO',title:'从代码候选，到经过检查的能力',steps:['冻结目标','独立检查','审阅发布'],symbol:'M8 5 2 12l6 7M16 5l6 7-6 7M14 2l-4 20',art:'<path d="M39 26h176v82H39ZM39 42h176M49 34h3M59 34h3M69 34h3"/><path class="accent" d="m85 57-18 16 18 16m72-32 18 16-18 16M133 54l-14 38"/><path class="code-cursor fx" d="M185 88h12"/><path class="faint" d="M68 117h119"/>'},
 tasks:{code:'EXECUTION QUEUE',title:'掌握执行进度，随时核对结果',steps:['已就绪','执行记录','结果接续'],symbol:'M4 4h16v4H4zM4 10h12v4H4zM4 16h8v4H4zM18 15l4 4-4 3',art:'<path d="M43 23h163v21H43zM43 55h132v21H43zM43 87h100v21H43z"/><path class="accent queue-marker fx" d="m182 59 14 7-14 7M54 33h70M54 65h52M54 97h32"/><path class="faint" d="M32 17v97M214 17v97"/>'},
 devices:{code:'DEVICE MESH',title:'让设备各司其职，连接保持可见',steps:['设备能力','共享范围','协议准备'],symbol:'M2 4h13v11H2zM6 15v5M3 20h9M18 9h4v12h-4zM15 7h5v2',art:'<path d="M23 31h100v61H23ZM59 92v13M42 105h42M173 45h40v68h-40ZM183 104h20"/><path class="faint" d="M123 61h23v18h27M146 61V22h34"/><circle class="accent" cx="187" cy="22" r="7"/><path d="M35 43h32M35 53h51M35 63h20"/>'},
 network:{code:'NETWORK BOUNDARY',title:'联网或离线，都有明确的边界',steps:['连接策略','云端通道','离线准备'],symbol:'M3 8a14 14 0 0 1 18 0M6 12a9 9 0 0 1 12 0M9 16a4 4 0 0 1 6 0M12 20h.1',art:'<path d="M124 24v83M117 24h14M117 107h14M42 59h23v27H42zM186 59h23v27h-23z"/><g class="network-waves fx"><path class="accent" d="M78 55q21 16 0 32M87 43q36 28 0 56M174 55q-21 16 0 32M165 43q-36 28 0 56"/></g><path class="faint" d="M30 116h194"/>'},
 modules:{code:'MODULE DOCK',title:'让能力独立升级，也能可靠回退',steps:['探测状态','版本切换','发布恢复'],symbol:'M3 3h7v18H3zM14 3h7v7h-7zM14 14h7v7h-7zM6 7v3M17 6h1M17 17h1',art:'<path class="faint" d="M38 16h176v101H38zM38 36h176"/><g class="dock-modules fx"><path d="M52 47h35v58H52ZM107 47h35v58h-35ZM162 47h35v58h-35Z"/><path class="accent" d="M60 57h19M115 57h19M170 57h19M60 66h19M115 66h19M170 66h19"/></g><path d="M49 26h4M60 26h4M71 26h4"/>'},
 private:{code:'PERSONAL BOUNDARIES',title:'让资料归属与使用范围始终清楚',steps:['资料归属','使用范围','适配准备'],symbol:'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8M5 21v-3a7 7 0 0 1 14 0v3M2 5v5M22 5v5',art:'<path class="faint" d="M39 19h174v96H39zM54 33h144v68H54z"/><circle class="accent" cx="126" cy="52" r="14"/><path class="accent" d="M97 95v-8a29 29 0 0 1 58 0v8M75 61h11M166 61h11"/><path d="M34 38V14h24M194 14h24v24M34 96v24h24M194 120h24V96"/>'}
};
function sectionIcon(id){const svg=icon('star');svg.classList.add('section-symbol');svg.querySelector('path').setAttribute('d',sectionDesigns[id].symbol);return svg;}
function sectionLead(id){
 const design=sectionDesigns[id],lead=el('section',undefined,'section-lead'),copy=el('div',undefined,'section-lead-copy');lead.dataset.visual=id;
 copy.append(el('div',design.code,'eyebrow'),el('h2',design.title));const steps=el('ol',undefined,'section-steps');for(const label of design.steps)steps.append(el('li',label));copy.append(steps);
 const art=document.createElementNS('http://www.w3.org/2000/svg','svg');art.setAttribute('viewBox','0 0 250 136');art.setAttribute('aria-hidden','true');art.classList.add('section-art');art.innerHTML=design.art;
 const figure=el('div',undefined,'section-figure');figure.append(art,el('small','功能示意','section-art-caption'));lead.append(copy,figure);return lead;
}
let appearanceSaving=false,monitorBusy=false,monitorClosed=false;
const drawings=[
 'M12 18H30V8H90V48H30V40H12M40 17H80M40 26H69M40 35H78M12 26L30 18L48 26L30 34ZM12 33L30 41L48 33',
 'M10 28L30 9L52 26L76 8L94 28L75 48L52 26L30 46L10 28M30 9V46M76 8L75 48',
 'M8 9H30L49 28H70M8 28H70M8 47H30L49 28M82 28H99M70 20H82V36H70Z',
 'M8 28H27L44 10H65L84 28H99M27 28L44 46H65L84 28M40 5H54V17H40ZM40 40H54V52H40Z',
 'M8 10H49V35H8ZM22 35V43H37M49 18H59L68 9H94M49 28H59L70 38M70 22H91V48H70Z',
 'M8 10H29L46 28H60M8 46H29L46 28M54 13L72 5L90 13L72 21ZM54 23L72 31L90 23M54 33L72 41L90 33M54 43L72 51L90 43'
];
function schematic(index,hero=false){
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',hero?'0 0 700 180':'0 0 104 56');svg.setAttribute('aria-hidden','true');svg.classList.add(hero?'control-traces':'domain-diagram');
 const data=hero?'M300 38H410L447 75H514M325 148H409L445 112H514M700 40H658L625 73H592M700 142H655L624 111H592M405 0V23L432 50H475M450 180V155L481 123':drawings[index];
 for(const cls of ['diagram-base','diagram-flow']){const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',data);path.classList.add(cls);svg.append(path);}return svg;
}
let navResizeObserver;
function positionNavigation(){
 const nav=$('settings-nav'),active=nav.querySelector('a[aria-current="page"]'),track=nav.querySelector('.nav-current-track');
 if(!active||!track)return;
 for(const [key,value] of Object.entries({x:active.offsetLeft,y:active.offsetTop,w:active.offsetWidth,h:active.offsetHeight}))track.style.setProperty('--nav-'+key,value+'px');
 track.classList.add('positioned');
}
function buildNavigation(){
 const nav=$('settings-nav');nav.replaceChildren();
 const entries=[{id:'home',title:'设置总览',code:'OVERVIEW',pages:['home']},...domains];
 for(const group of entries){
  const a=link('','#'+group.pages[0],'item'),frame=el('span',undefined,'nav-icon-shell'),copy=el('span',undefined,'nav-item-copy'),code=el('small',group.code,'nav-item-code');
  a.dataset.group=group.id;a.setAttribute('aria-label',group.title);code.setAttribute('aria-hidden','true');
  frame.append(group.id==='home'?icon('home'):sectionIcon(group.pages[0]));copy.append(el('span',group.title,'nav-item-title'),code);a.append(frame,copy);
  if(group.id!=='home'){const count=el('small',String(group.pages.length),'domain-count');count.title=group.pages.length+' 个子项';count.setAttribute('aria-hidden','true');a.append(count);}
  nav.append(a);
 }
 const track=el('div',undefined,'nav-current-track');track.setAttribute('aria-hidden','true');track.append(el('i',undefined,'nav-current-sweep'));nav.append(track);
 navResizeObserver?.disconnect();navResizeObserver=new ResizeObserver(positionNavigation);navResizeObserver.observe(nav);for(const a of nav.querySelectorAll('a.item'))navResizeObserver.observe(a);
}
function syncNavigation(){
 const group=domains.find(g=>g.pages.includes(tab));$('settings-group-name').textContent=group?.title||'总览';
 for(const a of $('settings-nav').querySelectorAll('a.item')){const active=a.dataset.group===(group?.id||'home');a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}
 positionNavigation();
 const sub=$('settings-subnav');sub.replaceChildren();sub.hidden=!group;
 if(group)for(const id of group.pages){const a=link('','#'+id,tab===id?'active':'');a.append(sectionIcon(id),el('span',pages[id][1]));if(tab===id)a.setAttribute('aria-current','page');sub.append(a);}
 $('page-eyebrow').textContent=group?.code||'CONTROL CENTER';
}
function themeChoices(){
 const grid=el('div',undefined,'theme-grid');for(const [id,title] of themes){const b=button('',()=>updateAppearance({theme:id}),'theme-choice');b.dataset.themeChoice=id;const swatch=el('div',undefined,'swatch '+id);swatch.setAttribute('aria-hidden','true');swatch.append(el('i'),el('i'),el('i'));b.append(swatch,el('span',title));grid.append(b);}return grid;
}
async function updateAppearance(patch){
 if(appearanceSaving)return;appearanceSaving=true;syncAppearance();
 try{snapshot.settings.ui=await savePreferences(patch);setSound(!!snapshot.settings.ui.sound);}finally{appearanceSaving=false;syncAppearance();}
}
function syncAppearance(){
 if(!snapshot)return;const ui=snapshot.settings.ui;
 for(const b of document.querySelectorAll('[data-theme-choice]')){const active=b.dataset.themeChoice===ui.theme;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));b.disabled=appearanceSaving;}
 for(const n of document.querySelectorAll('[data-preference]')){n.checked=n.dataset.preference==='motion_off'?!ui.motion_off:!!ui.sound;n.disabled=appearanceSaving;}
 const motion=$('settings-motion');if(motion){const label=ui.motion_off?'开启动效':'暂停动效';motion.setAttribute('aria-label',label);motion.dataset.tooltip=label;motion.title=label;motion.setAttribute('aria-pressed',String(!ui.motion_off));motion.disabled=appearanceSaving;}
 const sound=$('settings-sound');if(sound){const state=soundState(),label=state.enabled?(state.unlocked?'关闭交互音效':'音效已启用，点击解锁'):'开启交互音效';sound.setAttribute('aria-label',label);sound.dataset.tooltip=label;sound.title=label;sound.setAttribute('aria-pressed',String(state.enabled&&state.unlocked));sound.disabled=appearanceSaving;}
 const theme=$('settings-theme');if(theme){const label='主题与外观 · '+(themes.find(([id])=>id===ui.theme)?.[1]||'跟随系统');theme.setAttribute('aria-label',label);theme.dataset.tooltip=label;theme.title=label;}
}
function headerTools(){
 const host=$('settings-header-tools');const reload=iconButton('refresh','刷新当前状态',async()=>{reload.disabled=true;try{await refresh();}finally{reload.disabled=false;}});
 const sound=iconButton('sound','开启交互音效',async()=>{const old=soundState(),enabled=!(old.enabled&&old.unlocked);if(enabled){setSound(true);await unlockSound();}try{await updateAppearance({sound:enabled});}finally{setSound(!!snapshot.settings.ui.sound);syncAppearance();}});sound.id='settings-sound';
 const motion=iconButton('star','暂停动效',()=>updateAppearance({motion_off:!snapshot.settings.ui.motion_off}));motion.id='settings-motion';
 const theme=iconButton('settings','主题与外观',()=>{const m=modal('主题与外观');m.append(themeChoices(),link('更多外观与动效设置 →','#appearance'));m.querySelector('a').addEventListener('click',()=>$('modal').close());syncAppearance();});theme.id='settings-theme';host.append(reload,sound,motion,theme);
}
function overviewView(body){
 const hero=el('section',undefined,'control-hero'),copy=el('div',undefined,'control-copy'),brand=el('jarvis-logo');brand.className='control-logo';
 copy.append(el('div','JARVIS CONTROL CORE','eyebrow'),el('h2','有序协作，持续进化。'),el('p','连接你的模型、记忆与行动。','note'),el('span','核心状态见右上角','control-caption'));hero.append(schematic(0,true),copy,brand);body.append(hero);
 cleanup=resources(body);const stats=el('div',undefined,'control-summary');
 for(const [title,value] of [['模型通道',snapshot.settings.connections.length],['文字技能',skills.filter(s=>s.state==='ready'&&!s.adapter).length],['已发布能力',snapshot.status.releases.filter(x=>x.enabled).length]]){const s=el('span');s.append(el('strong',String(value)),el('span',title));stats.append(s);}body.append(stats);
 const grid=el('div',undefined,'domain-grid');domains.forEach((g,i)=>{const c=el('section',undefined,'domain-card'),a=link('','#'+g.pages[0],'domain-main'),art=el('div',undefined,'domain-art');art.append(schematic(i),el('span',String(i+1).padStart(2,'0'),'domain-index'));a.append(art,el('h2',g.title),el('p',g.note));c.append(a);const links=el('div',undefined,'domain-links');for(const id of g.pages)links.append(link(pages[id][1],'#'+id));c.append(links);grid.append(c);});body.append(grid);
 const stopResources=cleanup,observer=new IntersectionObserver(entries=>{for(const e of entries)e.target.dataset.inView=String(e.isIntersecting);});for(const c of grid.children)observer.observe(c);cleanup=()=>{stopResources();observer.disconnect();};
 body.append(el('p','资源读数来自本机；设置页不会因展示动效发起模型调用。','note control-footnote'));
}
function appearanceView(body){
 const layout=el('div',undefined,'appearance-layout'),themesCard=card('选择工作区配色','选择后立即应用，面板、表格与控件会一同变化。');themesCard.classList.add('appearance-palettes');themesCard.append(themeChoices());
 const effects=card('交互反馈','调整环境动态与声音，保持你习惯的节奏。');effects.classList.add('appearance-feedback');
 const motion=el('input');motion.type='checkbox';motion.dataset.preference='motion_off';motion.onchange=()=>run(()=>updateAppearance({motion_off:!motion.checked}));
 const sound=el('input');sound.type='checkbox';sound.dataset.preference='sound';sound.onchange=()=>run(async()=>{if(sound.checked){setSound(true);await unlockSound();}try{await updateAppearance({sound:sound.checked});}finally{setSound(!!snapshot.settings.ui.sound);syncAppearance();}});
 const preview=el('div',undefined,'workspace-sample');preview.setAttribute('aria-label','当前主题的工作区样式预览');
 const bar=el('div',undefined,'sample-toolbar');bar.append(el('i'),el('i'),el('i'),el('span','WORKSPACE'));
 const sample=el('div',undefined,'sample-body'),nav=el('div',undefined,'sample-nav'),content=el('div',undefined,'sample-content');for(let i=0;i<4;i++)nav.append(el('i'));
 content.append(el('strong','你的工作空间'),el('span','文字、面板与边界同步配色'),el('div',undefined,'sample-signal'));sample.append(nav,content);preview.append(bar,sample);
 effects.append(preview,field('环境与 Logo 动效',motion),field('交互音效',sound),el('p','原版 Logo 保持不变；状态与组装效果可在下方单独预览。','note'));
 const actions=el('div',undefined,'appearance-actions');actions.append(link('完整品牌状态预览 ↗','/brand/'),button('预览启动组装',()=>cinema(false,{preview:true})),button('预览离开拆散',()=>cinema(true,{preview:true})));effects.append(actions);layout.append(themesCard,effects);body.append(layout);syncAppearance();
}
async function monitor(){
 if(document.hidden||monitorBusy||monitorClosed)return;monitorBusy=true;
 try{const [health,task,development]=await Promise.all([get('/api/health'),get('/api/task-runner'),get('/api/development-runner')]);if(monitorClosed)return;const working=task.status==='running'||development.status==='running',state=health.control!=='ready'?'sleep':working?'thinking':'idle';document.body.dataset.controlState=state;brandState(state);$('settings-runtime-state').textContent=state==='sleep'?'核心已停止':working?'后台正在执行':'核心就绪 · 后台待命';}
 catch{if(!monitorClosed){document.body.dataset.controlState='offline';brandState('offline');$('settings-runtime-state').textContent='与核心连接中断';}}
 finally{monitorBusy=false;}
}
function heading(title,note=''){const n=el('div');n.append(el('h2',title));if(note)n.append(el('p',note,'note'));return n;}
function unavailable(title,text){const c=card(title,text);c.append(el('span','适配待接入','badge'));return c;}
function records(body,items,label){body.append(heading(label));if(!items.length)body.append(el('p','暂无记录。','empty'));for(const item of items){const c=card(item.capability||item.provider||item.id,(states[item.status]||item.status||'已登记')+' · '+(item.phase||item.model||item.id));c.append(button('查看实际记录',()=>details(label,item)));body.append(c);}}
function route(){
 cleanup();cleanup=()=>{};const requested=location.hash.slice(1)||'home';tab=['mcp','tools'].includes(requested)?'skill':requested;if(!pages[tab])tab='home';
 const id=tab==='skill'&&['mcp','tools'].includes(requested)?requested:tab,previous=document.body.dataset.settingsPage;
 document.body.dataset.settingsPage=id;document.body.dataset.settingsDomain=domains.find(g=>g.pages.includes(tab))?.id||'home';
 document.title=pages[tab][1]+' · Jarvis';$('page-title').textContent=pages[tab][1];$('page-subtitle').textContent=pages[tab][2];syncNavigation();
 const body=$('settings-body');body.replaceChildren();body.classList.remove('settings-enter');void body.offsetWidth;body.classList.add('settings-enter');
 if(previous!==id){document.querySelector('.settings-main').scrollTop=0;if(document.scrollingElement)document.scrollingElement.scrollTop=0;}
 if(tab==='home'){render(body);return;}
 const lead=sectionLead(id),content=el('div',undefined,'settings-page-content');body.append(lead,content);render(content);
 const stop=cleanup,observer=new IntersectionObserver(entries=>{for(const e of entries)e.target.dataset.inView=String(e.isIntersecting);});observer.observe(lead);cleanup=()=>{stop();observer.disconnect();};
}
function render(body){
 if(tab==='private'){run(async()=>{const {privateView}=await import('./settings-private.js');await privateView(body);});return;}
 if(tab==='local-models'){
  const mount=el('div');body.append(mount);mount.append(el('p','正在加载本地模型管理…','note'));let closed=false,stop=()=>{};cleanup=()=>{closed=true;stop();};
  import('./settings-local-models.js').then(({localModelsView})=>{if(closed)return;mount.replaceChildren();stop=localModelsView(mount);}).catch(()=>{if(!closed)mount.replaceChildren(card('本地模型模块暂未就绪','当前服务尚未加载此入口。模块更新完成后刷新即可，其他设置仍可使用。'));});return;
 }
 if(tab==='home'){overviewView(body);return;}
 if(tab==='appearance'){appearanceView(body);return;}
 if(tab==='skill'){const tabs=el('div',undefined,'tabs');for(const [id,label] of [['skill','技能目录'],['tools','本地工具'],['mcp','MCP 接入']]){const active=id==='skill'?!['#mcp','#tools'].includes(location.hash):location.hash==='#'+id,a=link('','#'+id,active?'active':'');a.append(sectionIcon(id),el('span',label));tabs.append(a);}body.append(tabs);if(location.hash==='#tools'){cleanup=toolsView(body);return;}if(location.hash==='#mcp'){run(()=>extensionsView(body,'mcp'));return;}body.append(heading('技能目录','独立能力直接使用，组合方法统一管理。点击查看使用条件。'));const intro=card('✦ 默认可用，不等于每次都调用','任务匹配 → 检查启用状态与依赖 → 加载指导或使用已接入的执行器 → 记录实际结果。技能不自行授予文件、桌面或命令执行权限。');body.append(intro);const search=input('','搜索技能、用途或组件…');search.type='search';search.setAttribute('aria-label','搜索技能');const kind=select([['','全部类型'],['独立技能','独立技能'],['组合技能','组合技能']]);kind.setAttribute('aria-label','技能类型');const searchrow=el('div',undefined,'search-row');searchrow.append(search,kind);body.append(searchrow);const categories=el('div',undefined,'tabs'),count=el('p',undefined,'note'),grid=el('div',undefined,'grid');let category='';const draw=()=>{grid.replaceChildren();const selected=skills.filter(s=>(!category||s.category===category)&&(!kind.value||s.kind===kind.value)&&(s.name+s.description).includes(search.value));count.textContent='显示 '+selected.length+' / '+skills.length+' 个技能 · '+skills.filter(s=>s.state==='ready'&&!s.adapter).length+' 个文字流程可用';for(const s of selected){const c=card(s.name,s.description);c.classList.add('skill-card');if(s.icon){const mark=el('span',s.icon,'personal-skill-icon');mark.title=s.use_when||s.description;mark.dataset.tooltip=s.use_when||s.description;mark.tabIndex=0;mark.setAttribute('role','img');mark.setAttribute('aria-label',s.name+'：'+(s.use_when||s.description));c.prepend(mark);}c.prepend(el('span',s.kind,'badge'));c.append(el('p',s.output,'note'),el('span',s.state==='ready'?(s.enabled?(s.adapter==='anatomy-fixed'?'机械与场可用 · 示例零调用':s.adapter==='blender-studio'?'Blender 工作室 · 依赖按次检查':'按条件启用 · 需模型'):'已停用'):'新适配器待接入','badge'));const actions=el('div',undefined,'row');actions.append(button('使用条件',()=>{const m=modal(s.name);m.append(el('p',s.description));if(s.use_when)m.append(el('h3','什么时候使用'),el('p',s.use_when));if(s.avoid_when)m.append(el('h3','什么时候不使用'),el('p',s.avoid_when));if(s.examples?.length){m.append(el('h3','开始方式'));for(const example of s.examples)m.append(el('p',example,'note'));m.append(el('p','在聊天的技能选择中选中本技能，可在同一会话持续练习或复盘。','note'));}m.append(el('h3','工作方式'),el('p',s.guidance||'需要独立实现与验证对应的执行适配器。','note'),el('p',s.triggers.length?(s.auto_patterns?'自动匹配明确请求开头（引述、否定和假设不匹配）：':'自动匹配关键词：')+s.triggers.join('、'):'没有启用自动匹配。','note'));}));if(s.state==='ready')actions.append(button(s.enabled?'停用':'启用',async()=>{await post('/api/skill/enable',{id:s.id,enabled:!s.enabled});skills=await get('/api/skills');draw();}));if(s.source){c.append(link('来源：'+s.source.name+' · '+s.source.license,s.source.url));}if(s.adapter==='google-image'){const mark=el('span','🍌','studio-logo studio-card-mark');mark.title=s.guidance;mark.setAttribute('aria-label','Nano Banana图片技能');c.prepend(mark);if(s.enabled)actions.append(button('打开图片工作室',async()=>{try{const {imageStudio}=await import('./settings-images.js');await imageStudio(snapshot.settings);}catch(e){notice('图片工作室尚未加载，请在正常重启Jarvis后使用。');}}));}if(s.adapter==='gmail-mailbox'&&s.enabled)actions.append(button('打开 Gmail 助手',()=>{location.hash='mail';}));if(s.adapter==='blender-studio'){const mark=el('span','◈','studio-logo studio-card-mark');mark.title=s.guidance;mark.dataset.tooltip=s.description;mark.tabIndex=0;mark.setAttribute('aria-label','3D 工作室使用说明');c.prepend(mark);if(s.enabled)actions.append(button('打开 3D 工作室',()=>studio3d(snapshot.settings)));}if(s.adapter==='anatomy-fixed'&&s.enabled){actions.append(button('打开机械与场实验台',()=>anatomyStudio(snapshot.settings)));for(const mechanism of (s.mechanisms||[{id:'slider-crank',name:'曲柄滑块演示'}])){actions.append(button('制作'+mechanism.name,async()=>{const result=await post('/api/anatomy/render',{mechanism:mechanism.id});c.append(link(mechanism.id==='slider-crank'?'打开机械演示 ↗':'打开'+mechanism.name+' ↗',result.url),el('p','产物已保存 · '+(result.configuration?.mode||mechanism.id)+' · SHA-256: '+result.sha256,'note'));}));}}c.append(actions);grid.append(c);}};for(const name of ['',...new Set(skills.map(s=>s.category))]){const b=button(name||'全部技能',()=>{category=name;for(const item of categories.children)item.classList.remove('active');b.classList.add('active');draw();},name?'':'active');categories.append(b);}search.oninput=draw;kind.onchange=draw;body.append(categories,count,grid);draw();run(()=>extensionsView(body,'skill'));return;}
 if(tab==='mail'){run(async()=>{cleanup=await mailboxView(body);});return;}
 if(tab==='models'){if(snapshot.settings.configured)modelManager.models(body);else body.append(card('模型连接尚未配置','请先按工程模型接入说明初始化配置。'));return;}
 if(tab==='connections'){modelManager.connections(body);return;}
 if(tab==='calls'||tab==='overview'){usageView(body,[...usage,...snapshot.calls],tab==='overview');return;}
 if(tab==='tasks'){const live=el('section');body.append(live);cleanup=workStatusView(live,{settings:true});const ledger=el('details');ledger.append(el('summary','任务创建与历史账本'));const content=el('div');ledger.append(content);body.append(ledger);runtimeView(content,snapshot,refresh);return;}
 if(tab==='network'){run(()=>networkView(body,snapshot.settings));return;}
 if(tab==='plans'){cleanup=goalsView(body,{settings:snapshot.settings});return;}
 if(tab==='memory'){run(async()=>{const projects=await get('/api/projects');if(body.isConnected&&tab==='memory')await memoryView(body,{settings:snapshot.settings,projects});});return;}
 if(tab==='coding'){cleanup=developmentView(body,snapshot.settings);body.append(card('外部 Codex 适配','外部 Codex 已可在研发的编码模型选择中使用，返回候选代码并交由原检查和发布流程处理。使用本机 Codex 登录状态；不会迁移账号令牌。桌面执行仍待接入。'),button('查看保留的 Codex 偏好',()=>details('编码偏好',snapshot.settings.coding)),button('编辑编码偏好',()=>modelManager.edit('外部 Codex 编码偏好',fields=>{const c=snapshot.settings.coding,model=input(c.model||''),reasoning=select(['low','medium','high','xhigh','max'].map(x=>[x,x]),c.reasoning||'medium'),enabled=el('input');enabled.type='checkbox';enabled.checked=!!c.enabled;fields.append(field('模型',model),field('推理档位',reasoning),field('保留启用偏好',enabled),el('p','执行适配尚未接通；保存偏好不会启动外部软件。','note full'));return()=>({action:'coding',enabled:enabled.checked,model:model.value,reasoning:reasoning.value});})));return;}
 if(tab==='modules'){runtimeView(body,snapshot,refresh,'modules');body.append(link('本地模型：下载、运行和修复','#local-models'));body.append(card('连续身份与控制核心','身份状态、授权、停止与恢复独立于可替换能力。工作台不直接改写自身源码或发布候选。'));return;}
 if(tab==='growth'){const tabs=el('div',undefined,'tabs'),content=el('div',undefined,'growth-content');let stopEvolution=()=>{};cleanup=()=>stopEvolution();const display=name=>{stopEvolution();stopEvolution=()=>{};content.replaceChildren();if(name==='自检'){runtimeView(content,snapshot,refresh,'modules');content.append(card('当前核心状态',snapshot.status.control==='ready'?'核心就绪':'核心已停止'),button('刷新检查记录',async()=>{snapshot=await get('/api/snapshot');display(name);}),button('查看完整状态',()=>details('核心状态',snapshot.status)));}else if(name==='自愈'){content.append(card('恢复与接续','启动恢复会把中断的模型调用标为未知，保留回执；未知调用不会自动重发。已发布能力通过新核心恢复流程回退。'));runtimeView(content,snapshot,refresh);records(content,snapshot.packages,'能力与恢复记录');}else{stopEvolution=developmentView(content,snapshot.settings);}};for(const name of ['自检','自愈','进化']){const b=button(name,()=>{for(const x of tabs.children)x.classList.remove('active');b.classList.add('active');display(name);},name==='自检'?'active':'');tabs.append(b);}body.append(tabs,content);display('自检');return;}
 const pending={devices:['设备与共同体','新工程共同体协议和跨设备许可尚未运行。此页保留设备与分域共享的入口，不连接旧节点。'],private:['人员与私密资料','本机模型凭据已加密保存。关系资料、身份验证及私密资料库尚未迁入；不能以此界面代替本人身份验证。'],network:['网络与离线','云端通道已接入，本地模型运行器尚未准备。旧工程应用级离线开关没有复制，新核心网络策略需要单独实现和验证。']};body.append(unavailable(...pending[tab]));
}
async function boot(){
 initModal();[snapshot,skills,usage]=await Promise.all([get('/api/snapshot'),get('/api/skills'),get('/api/usage')]);applyPreferences(snapshot.settings.ui);setSound(!!snapshot.settings.ui.sound);$('version').textContent='v'+snapshot.status.release;buildNavigation();headerTools();syncAppearance();window.addEventListener('hashchange',()=>run(route));route();monitor();
 const timer=setInterval(monitor,5000);document.addEventListener('visibilitychange',monitor);
 const channel=new BroadcastChannel('jarvis-workbench-settings');channel.onmessage=()=>run(async()=>{const fresh=await get('/api/snapshot');if(monitorClosed)return;snapshot.settings=fresh.settings;applyPreferences(snapshot.settings.ui);setSound(!!snapshot.settings.ui.sound);syncAppearance();});
 const system=matchMedia('(prefers-color-scheme: dark)');const systemChange=()=>{if(snapshot.settings.ui.theme==='system')applyPreferences(snapshot.settings.ui);};system.addEventListener('change',systemChange);document.addEventListener('jarvis-sound',syncAppearance);
 window.addEventListener('pagehide',()=>{monitorClosed=true;cleanup();navResizeObserver?.disconnect();clearInterval(timer);channel.close();document.removeEventListener('visibilitychange',monitor);system.removeEventListener('change',systemChange);document.removeEventListener('jarvis-sound',syncAppearance);});
 window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
}
run(boot);
