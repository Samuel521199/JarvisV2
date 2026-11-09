export function offsetText(minutes){
 const sign=minutes<0?'-':'+';minutes=Math.abs(minutes);
 return sign+String(Math.floor(minutes/60)).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0');
}
export function exactTime(local,offset){
 if(!local)return null;
 if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(local)||!/^([+-])(0\d|1[0-4]):[0-5]\d$/.test(offset)||(/^[-+]14:/.test(offset)&&!offset.endsWith(':00')))throw Error('请填写日期时间和有效的固定UTC偏移。');
 return local+':00'+offset;
}
