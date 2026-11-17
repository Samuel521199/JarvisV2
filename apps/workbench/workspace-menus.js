import {el,button,field,input,modal,closeModal,contextMenu,confirmAction,notice,get,download} from './ui.js';
export function conversationMenu(item,anchor,{change,folders,panel}){
 const rename=()=>{const body=modal('重命名会话'),name=input(item.title);name.maxLength=100;body.append(field('会话名称',name),button('保存名称',async()=>{await change(item,{title:name.value.trim()});closeModal();},'primary'));name.focus();name.select();};
 return contextMenu(item.title,anchor,[
  {icon:'pin',label:item.pinned?'取消置顶':'置顶会话',action:()=>change(item,{pinned:!item.pinned})},
  {icon:'edit',label:'重命名',action:rename},null,
  {icon:'folder',label:'会话专属文件夹',action:()=>folders.view(panel('会话专属文件夹'),item.id)},
  {icon:'copy',label:'复制会话链接',action:async()=>{await navigator.clipboard.writeText(location.origin+'/#chat='+item.id);notice('已复制本机会话链接。');}},
  {icon:'file',label:'导出会话',action:async()=>{const value=await get('/api/chats/'+item.id);download(item.id+'.md','# '+value.title+'\n\n'+value.turns.map(t=>'## 你\n\n'+t.request.text+'\n\n## Jarvis\n\n'+(t.reply||'（本轮暂无回答）')).join('\n\n'));}},null,
  {icon:'archive',label:item.archived?'取消归档':'归档会话',action:async()=>{await change(item,{archived:!item.archived});notice(item.archived?'会话已取消归档。':'会话已归档，可从“归档与已删除”恢复。');}},
  {icon:'trash',label:'删除会话',danger:true,action:()=>confirmAction('删除会话？','“'+item.title+'”将移入“归档与已删除”，可随时恢复。内容和文件保留；不会取消后台任务。','移入已删除',async()=>{await change(item,{removed:true});notice('会话已移入已删除，可随时恢复。');})}
 ]);
}
