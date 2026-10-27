import assert from 'node:assert/strict';
import {planetaryState,externalProfile,internalSector} from '../modules/skills/anatomy/planetary-model.mjs';
const rotate=(p,a,x=0,y=0)=>p.map(([u,v])=>[x+u*Math.cos(a)-v*Math.sin(a),y+u*Math.sin(a)+v*Math.cos(a)]);
function inside([x,y],polygon){let yes=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){const [xi,yi]=polygon[i],[xj,yj]=polygon[j];if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)yes=!yes;}return yes;}
let checked=0,overlaps=0;const counts={sun:0,ring:0,reverse:0};let worstRing=0;const examples=[];
for(const [S,P] of [[24,18],[18,18],[24,24],[20,19]]){
 const R=S+2*P,sun=externalProfile(S),planet=externalProfile(P),sector=internalSector(R).filter(([x,y])=>Math.hypot(x,y)<R+3);
 function ringBoundary(theta){const pitch=Math.PI*2/R;theta=((theta+pitch/2)%pitch+pitch)%pitch-pitch/2;const direction=[Math.cos(theta),Math.sin(theta)];
  // Intersect the radial ray with the actual sampled inner-tooth contour.
  for(let i=1;i<sector.length;i++){const a=sector[i-1],b=sector[i],ex=b[0]-a[0],ey=b[1]-a[1],den=direction[0]*ey-direction[1]*ex;if(Math.abs(den)<1e-12)continue;const t=(a[0]*ey-a[1]*ex)/den,u=(a[0]*direction[1]-a[1]*direction[0])/den;if(t>0&&u>=-1e-8&&u<=1+1e-8)return t;}
  throw Error('no ring boundary');}
 for(const mode of ['ring-fixed','sun-fixed','carrier-fixed'])for(let a=0;a<=720;a+=12){
  const q=planetaryState({sun_teeth:S,planet_teeth:P,mode},a);const sp=rotate(sun,q.sunAngle);
  for(const item of q.planets){const pp=rotate(planet,item.angle,item.x,item.y);
   for(const v of pp){if(Math.hypot(...v)<S+2-1e-8&&inside(v,sp)){overlaps++;counts.sun++;if(examples.length<4)examples.push({S,P,mode,a,v});}const angle=Math.atan2(v[1],v[0])-q.ringAngle;if(Math.hypot(...v)>ringBoundary(angle)+1e-6){overlaps++;counts.ring++;worstRing=Math.max(worstRing,Math.hypot(...v)-ringBoundary(angle));}checked++;}
   for(const v of sp)if(Math.hypot(v[0]-item.x,v[1]-item.y)<P+2-1e-8&&inside(v,pp)){overlaps++;counts.reverse++;}
  }
 }
}
console.log({counts,worstRing,examples});assert.equal(overlaps,0,'sampled tooth vertices penetrate sun/planet/ring polygons');
console.log(JSON.stringify({status:'passed',poses:4*3*61,vertex_checks:checked,penetrations:overlaps,limits:'Four declared tooth sets, 12 degree input increments; 2D vertex screening only, not exact swept 3D interference or root strength verification.'}));
