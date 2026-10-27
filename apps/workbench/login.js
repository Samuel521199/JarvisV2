import {$,get,notice,identityChanged,link} from './ui.js';
const status=await get('/api/family/status');
if(!status.enabled){$('login-form').hidden=true;$('login-state').append(link('家庭登录尚未启用，前往工作台设置。','/settings#private'));}
else if(status.actor)location.replace(status.actor.role==='owner'?'/':'/family');
$('login-form').addEventListener('submit',async event=>{
 event.preventDefault();$('login-submit').disabled=true;
 try{const response=await fetch('/api/family/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:$('identity').value.trim(),password:$('password').value})});const result=await response.json();$('password').value='';if(!response.ok)throw Error(result.error==='family_rate'?'尝试次数过多，请一分钟后再试。':'身份或密码不正确。');identityChanged();location.replace(result.actor.role==='owner'?'/':'/family');}
 catch(error){notice(error.message);}finally{$('login-submit').disabled=false;}
});
