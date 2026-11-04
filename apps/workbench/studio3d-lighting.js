// Pure bounded geometry for rotating only the existing inspection key light.
export function keyLightOffset(degrees, span) {
 if(typeof degrees!=='number'||!Number.isFinite(degrees)||degrees < -180||degrees > 180)throw Error('主光方位必须为 -180 到 180 度');
 if(typeof span!=='number'||!Number.isFinite(span)||span<=0)throw Error('无效模型范围');
 const a=degrees*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
 return [(-.5*c+.8*s)*span,1.2*span,(.5*s+.8*c)*span];
}
