// Presentation projection only; no commands or model calls.
export const brandLabels=Object.freeze({idle:'待命',thinking:'思考',sleep:'休眠',offline:'连接中断'});
export function projectBrand({connected=true,control='ready',pending=false,turns=[],away=false}={}){
 if(!connected)return 'offline';
 if(away||control!=='ready')return 'sleep';
 return pending||turns.some(t=>['READY','RUNNING'].includes(t.status))?'thinking':'idle';
}
