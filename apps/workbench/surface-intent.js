// Only local, read-only navigation. Quoted or ambiguous requests reach normal chat.
export function surfaceIntent(text){
 text=String(text||'').trim();
 if(text.length>45||/[“”"「」『』]|不要|别|不想|怎么|如何|实现|代码|如果|假如|为什么/.test(text))return null;
 text=text.replace(/[，。！？?!、\s]/g,'');
 if(/^(?:请|帮我|给我)?(?:打开|看看|查看|显示)(?:一下)?(?:邮箱|邮件|我的邮件|我的邮箱)$/.test(text))return 'mail';
 if(/^(?:请|帮我|给我)?(?:看看|查看|显示|打开)(?:一下)?(?:任务|工作状态|任务进度|工作进度|进度|正在做的事|未读结果|新结果)$/.test(text)||/^(?:你|Jarvis)?(?:在忙什么|做到哪了|做到哪里了|有什么新结果|有什么未读结果)$/.test(text))return 'work';
 if(/^(?:请|帮我|给我)?(?:打开|看看|查看|显示)(?:一下)?(?:项目|项目列表|我的项目|会话列表|项目和会话)$/.test(text))return 'projects';
 return null;
}
