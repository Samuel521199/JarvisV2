import {el,field,input,button,link,get,post,notice,card} from './ui.js';
export async function privateView(body){
 const status=await get('/api/family/status');
 const summary=card('家庭身份与私密空间',status.enabled?'家庭登录已启用。主人的普通工作台也需要登录；成员只进入自己的家庭空间。':'当前沿用本机操作者模式。启用家庭登录后，普通工作台和所有数据接口都会进行身份检查。');body.append(summary);
 summary.append(el('p','固定规则：主人可管理并查看全部；家人只看自己的和明确共享内容。现有普通会话及知识库不会自动搬入加密库。','note'));
 if(status.enabled){summary.append(link('打开家庭私密空间','/family'),button('退出并锁定当前身份',async()=>{await post('/api/family/logout',{});location.assign('/login');}));return;}
 const password=input();password.type='password';password.autocomplete='new-password';password.minLength=12;password.maxLength=256;
 const again=input();again.type='password';again.autocomplete='new-password';again.maxLength=256;
 summary.append(field('设置主人密码（12～256 字符，请自行保存）',password),field('再次输入密码',again));
 summary.append(el('p','本机私密库采用 Windows DPAPI；同一 Windows 账户下的其他程序仍属于受信任边界。当前没有密码找回、跨设备恢复和 Mac 密钥适配，请先保存好密码。','note'));
 const enable=button('启用家庭登录与私密空间',async()=>{if(password.value!==again.value||password.value.length<12){notice('两次密码需要一致且至少 12 字符。');return;}enable.disabled=true;try{await post('/api/family/setup',{password:password.value,policy:status.policy});password.value=again.value='';location.assign('/family');}finally{enable.disabled=false;}});summary.append(enable);
}
