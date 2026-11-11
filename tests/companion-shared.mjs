import assert from 'node:assert/strict';
import {conversationGroups} from '../apps/workbench/conversation-groups.js';
import {surfaceIntent} from '../apps/workbench/surface-intent.js';
const groups=conversationGroups([{id:'p',name:'真实项目',path:'/projects/p'},{id:'gone',removed:1}],
 [{id:'a',project_id:'p'},{id:'b',project_id:''},{id:'c',project_id:'p',archived:1},{id:'d',project_id:'gone'},{id:'e',removed:1}]);
assert.equal(groups.length,2);assert.deepEqual(groups[0].chats.map(c=>c.id),['a']);assert.deepEqual(groups[1].chats.map(c=>c.id),['b']);
for(const [text,value] of [['你在忙什么？','work'],['帮我看看任务进度','work'],['看看未读结果','work'],['打开我的邮箱','mail'],['看看项目','projects']])assert.equal(surfaceIntent(text),value,text);
for(const text of ['不要打开邮件','怎么实现打开邮箱','如果打开项目会怎样','帮我写一个任务系统','停止所有任务','删除邮件','“打开邮箱”是什么意思','打开我的邮箱并删除所有邮件'])assert.equal(surfaceIntent(text),null,text);
console.log('Shared groups and conservative natural navigation passed');
for(const text of ['帮我定时检查重要邮件','每天帮我看看邮箱','有空'])assert.equal(surfaceIntent(text),text==='有空'?null:'mail-standing',text);
for(const text of ['不要定时检查邮件','怎么实现自动检查邮件','如果每天检查邮件会怎样','“定时检查邮件”是什么','自动检查邮件并发送回复'])assert.equal(surfaceIntent(text),null,text);
console.log('Shared mail-standing navigation stays an inert entry, not authorization');
