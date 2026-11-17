import {el,button,get,post,modal,details,markdown,outcomeView,completionView} from './ui.js';
import {watchReply,workApi} from './work-client.js';

const labels={finished:'执行已结束',failed:'执行遇到问题',cancelled:'已经取消',running:'正在进行',queued:'正在排队',needs_input:'等待你确认',waiting:'等待条件',external:'等待外部响应',unknown:'结果需要核对'};
export async function openWorkResult(unit,{onOpenChat=null,refresh=()=>{}}={}){
 const body=modal(unit.title);body.classList.add('work-result');
 body.append(el('p',unit.project_name+(unit.chat_title?' / '+unit.chat_title:''),'work-breadcrumb'));
 const loading=el('p','正在读取原始成果…','note');body.append(loading);
 let shown=0;
 try{
  const chats=new Map();
  for(const item of unit.members){
   const section=el('section',undefined,'work-result-entry');let raw=item,readable=false,attention=item.attention;
   section.append(el('h3',item.title),el('p',labels[item.state]||'工作反馈','note'));
   if(item.source==='dialogue'){
    const id=item.context?.chat_id||item.chat_id;
    if(!chats.has(id))chats.set(id,await get('/api/chats/'+encodeURIComponent(id)));
    const turn=chats.get(id).turns.find(t=>t.id===item.id);
    if(turn){raw=turn;attention=turn.attention;section.append(el('p',turn.request?.text||'原会话中的任务','work-request'));
     if(turn.reply){section.append(markdown(turn.reply));readable=true;}
     else if(turn.error)section.append(el('p','这次回复未完成，请在原会话核对。','note'));
    }
   }else if(item.source==='tasks'){
    raw=await post('/api/operations',{action:'task_detail',id:item.id});
    section.append(el('p',raw.task?.body?.goal||item.title));
    for(const action of raw.actions||[]){if(action.result!=null){section.append(el('h4','步骤成果'),el('pre',typeof action.result==='string'?action.result:JSON.stringify(action.result,null,2),'work-output'));readable=true;}}
    outcomeView(section,raw.outcome,{taskId:item.id,refresh});completionView(section,raw.completion,{refresh});
   }else if(item.source==='studio3d'||item.source==='images'){
    const path=item.source==='studio3d'?'/api/studio3d/jobs/':'/api/image-studio/jobs/';
    raw=await get(path+encodeURIComponent(item.id));const receipt=raw.receipt;
    section.append(el('p',receipt?.title||raw.phase||item.reason||'结果保存在原工作室中。'));
    if(item.source==='studio3d'&&receipt?.files?.['preview.png']){const img=el('img');img.src='/api/studio3d/files/'+encodeURIComponent(item.id)+'/preview.png';img.alt=receipt.title||'本次模型的实际预览';img.className='work-artifact-preview';section.append(img);readable=true;}
    if(item.source==='studio3d'&&receipt?.files?.['model.glb']){const a=el('a','打开交互模型');a.href='/api/studio3d/view/'+encodeURIComponent(item.id);a.target='_blank';a.rel='noopener';a.className='work-result-link';section.append(a);}
    if(receipt?.unfulfilled?.length)section.append(el('p','仍需核对：'+receipt.unfulfilled.join('；'),'note'));
   }else if(item.reason)section.append(el('p',item.reason));
   // Technical receipts remain available, but never replace the human result.
   const technical=el('details',undefined,'work-technical');technical.append(el('summary','原始回执与技术记录'),el('pre',JSON.stringify(raw,null,2)));section.append(technical);
   if(item.attention?.unread&&!readable)section.append(button('这一项已看完',async()=>{await workApi.viewed(item);await refresh();},'work-read-action'));
   body.append(section);shown++;
   // Only actual displayed results use the same visibility receipt as chat.
   // Opening a list, hovering or collapsing the panel never acknowledges it.
   if(readable)watchReply(section,attention);
  }
  if(unit.chat_id){const open=button('到原会话继续',()=>{if(onOpenChat){document.getElementById('modal').close();onOpenChat(unit.chat_id);}else location.href='/#chat='+encodeURIComponent(unit.chat_id);},'work-result-link');body.append(open);}
  if(!shown)body.append(el('p','当前成果暂不可用，请刷新后再查看。','note'));
 }catch(error){body.append(el('p','原始成果暂未读取成功，未自动标记已读：'+error.message,'form-error'));}
 finally{loading.remove();}
}
