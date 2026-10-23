import {MeshScene,vadd,vsub,vmul,unit,basis,ringPoint,flowParticles,flameVolume,projectStructure} from './structure3d.mjs';
const TAU=Math.PI*2,colors={steel:'#a8bfcd',dark:'#697f92',blue:'#6eacca',teal:'#7bb9ae',copper:'#dba06b',red:'#cf947e',water:'#4ebbdc'};
const point=(x,r,t)=>[x,r*Math.cos(t),r*Math.sin(t)];
function valveLift(phase,start){const u=(phase-start)/180;return u>0&&u<1?Math.sin(Math.PI*u)*10:0;}
function blade(scene,x,inner,outer,angle,width,twist,color){const a=point(x-width/2,inner,angle),b=point(x+width/2,inner,angle+.07),c=point(x+width/2+twist,outer,angle+.18),d=point(x-width/2+twist,outer,angle+.05);scene.face([a,b,c,d],color);scene.face([vadd(a,[0,.8,.8]),vadd(d,[0,.8,.8]),vadd(c,[0,.8,.8]),vadd(b,[0,.8,.8])],color);}
function engine3d(m,s,time,o,models){
 const g=new MeshScene(),p=m.params,r=p.crank_mm,L=r*p.rod_ratio,n=p.cylinders,step=105,start=-(n-1)*step/2,head=r+L+40,ex=o.explode||0;
 const part=(...args)=>g.part(...args),c=colors;
 part('block','气缸体与冷却水套','剖开外壳显示气缸衬套与水套；基本外形简化。','housing',[start,0,head/2],c.blue,[0,ex*38,0]);g.box([0,0,head*.45],[(n-1)*step+112,112,head*.87],c.blue);
 part('crankshaft','曲轴与曲柄销','各缸曲柄相位来自720°教学循环；连杆把活塞往复运动与曲轴旋转关联。','moving',[start-45,0,0],c.steel);g.cylinder([start-64,0,0],[start+(n-1)*step+64,0,0],r*.18,c.steel,12);
 for(let i=0;i<n;i++){const a=s.cylinders[i],x=start+i*step,y=a.pinX,z=a.pinZ;for(const dx of [-10,10])g.cylinder([x+dx,0,0],[x+dx,y,z],r*.24,c.dark,8);g.cylinder([x-14,y,z],[x+14,y,z],r*.19,c.steel,10);}
 part('bearings','主轴承与支承座','支承曲轴主轴颈；未计算油膜和轴承载荷。','fixed',[start-47,0,0],c.copper);for(const x of [start-45,start+(n-1)*step+45]){g.tube([x-7,0,0],[x+7,0,0],r*.34,r*.2,c.copper,14);g.box([x,0,-r*.6],[20,65,14],c.dark);}
 part('timing','正时带与2:1带轮','四冲程凸轮轴每720°曲轴转动一周；带轮和带为示意。','moving',[start-64,0,head+30],c.dark,[0,0,ex*14]);
 const tx=start-66,camZ=head+35;g.cylinder([tx-3,0,0],[tx+3,0,0],20,c.dark,18);g.cylinder([tx-3,0,camZ],[tx+3,0,camZ],40,c.dark,18);g.line([[tx,20,0],[tx,40,camZ],[tx,-40,camZ],[tx,-20,0],[tx,20,0]],'#546f80',3);g.line([[tx-4,0,0],[tx-4,18*Math.cos(s.angle*Math.PI/180),18*Math.sin(s.angle*Math.PI/180)]],'#e7bd7c',3);g.line([[tx-4,0,camZ],[tx-4,36*Math.cos(s.angle*Math.PI/360),camZ+36*Math.sin(s.angle*Math.PI/360)]],'#e7bd7c',3);
 part('camshafts','双顶置凸轮轴','转速是曲轴的一半；凸轮几何是教学外形，升程使用理想分阶段正弦函数。','moving',[0,-24,camZ],c.copper,[0,0,ex*55]);for(const y of [-24,24])g.cylinder([start-45,y,camZ],[start+(n-1)*step+45,y,camZ],5,c.copper,10);
 for(let i=0;i<n;i++){
  const a=s.cylinders[i],x=start+i*step,pz=a.piston,phase=a.phase;
  part('liner-'+i,'缸'+(i+1)+' · 衬套','缸孔、活塞与水套之间保留可见间隙；没有接触/制造公差解。','housing',[x,0,head*.6],c.steel,[0,ex*38,0]);g.tube([x,0,L-r-22],[x,0,head-10],44,40,c.steel,16);
  part('piston-'+i,'缸'+(i+1)+' · 活塞与活塞环','高度直接使用连杆几何计算；活塞环形状示意。','moving',[x,0,pz],c.blue,[0,0,ex*18]);g.cylinder([x,0,pz-24],[x,0,pz+8],36,c.blue,16);for(const z of [-2,3])g.tube([x,0,pz+z],[x,0,pz+z+2],37,35,c.dark,16);g.cylinder([x-39,0,pz-6],[x+39,0,pz-6],5,c.steel,10);
  part('rod-'+i,'缸'+(i+1)+' · 连杆','大小头中心间距等于设定连杆长度；活塞销绘制偏移仅为外形。','moving',[x,a.pinX/2,(a.pinZ+pz)/2],c.steel);g.cylinder([x,a.pinX,a.pinZ],[x,0,pz],7,c.steel,8);g.tube([x-7,a.pinX,a.pinZ],[x+7,a.pinX,a.pinZ],13,8,c.copper,12);
  part('head-'+i,'缸'+(i+1)+' · 缸盖','阀座、进排气口与火花塞的教学结构。','housing',[x,0,head],c.blue,[0,0,ex*85]);g.box([x,0,head],[92,99,18],c.blue);
  const inLift=valveLift(phase,0),outLift=valveLift(phase,540);
  for(const [name,y,lift] of [['intake',-23,inLift],['exhaust',23,outLift]]){
   part(name+'-'+i,'缸'+(i+1)+(name==='intake'?' · 进气门':' · 排气门'),'气门只在对应理想冲程中打开；未建模提前/迟闭或重叠。','moving',[x,y,head-12-lift],name==='intake'?c.teal:c.copper,[0,0,ex*55]);g.cylinder([x,y,head-15-lift],[x,y,head+28-lift],3,c.steel,8);g.cylinder([x,y,head-18-lift],[x,y,head-14-lift],14,name==='intake'?c.teal:c.copper,12);
   const spring=[];for(let j=0;j<=40;j++){const t=j/40;spring.push([x+7*Math.cos(t*TAU*5),y+7*Math.sin(t*TAU*5),head+4+t*17-lift]);}g.line(spring,'#8ba0ae',1.1);
   part('cam-'+name+'-'+i,(name==='intake'?'进气':'排气')+'凸轮 '+(i+1),'随半速凸轮轴旋转的简化偏心轮；与气门理想升程同周期。','moving',[x,y,camZ],c.copper,[0,0,ex*55]);const ca=phase*Math.PI/360+(name==='exhaust'?Math.PI/2:0);g.cylinder([x-7,y+3*Math.cos(ca),camZ+3*Math.sin(ca)],[x+7,y+3*Math.cos(ca),camZ+3*Math.sin(ca)],9,c.copper,12);
  }
  part('plug-'+i,'缸'+(i+1)+' · 火花塞','火花只在理想做功开始附近显示；不计算点火提前角。','fixed',[x,0,head+12],c.steel,[0,0,ex*55]);g.cylinder([x,0,head-7],[x,0,head+22],4,c.steel,8);g.cylinder([x,0,head+14],[x,0,head+27],6,'#e8e7da',8);
  part('ports-'+i,'缸'+(i+1)+' · 进排气歧管','气体沿管道和开启的气门进入/离开气缸。','housing',[x,-62,head],c.teal,[0,ex*30,ex*55]);g.tube([x,-90,head-5],[x,-23,head-5],15,11,c.teal,10);g.tube([x,23,head-5],[x,90,head-5],15,11,c.copper,10);
  const chamberLow=pz+12,chamberHigh=head-18;
  part('gas-'+i,'缸'+(i+1)+' · 燃烧室气体','空间粒子与火焰体仅示意阶段和路径；没有化学反应、温度或压力求解。','fluid',[x,0,chamberHigh],c.red);
  if(o.effects&&m.effects.includes('airflow')){if(a.intake)flowParticles(g,[[x,-95,head-5],[x,-23,head-5],[x,-23,chamberHigh-8],[x,0,chamberLow+5]],time,{count:22,speed:1.4,color:'#54c5e8',spread:1.2});if(a.exhaust)flowParticles(g,[[x,0,chamberLow+4],[x,23,chamberHigh-8],[x,23,head-5],[x,95,head-5]],time,{count:22,speed:1.4,color:'#b99de3',spread:1.2});}
  if(o.effects&&m.effects.includes('flame')&&a.flame>0&&chamberHigh>chamberLow)flameVolume(g,[x,0,chamberHigh],[x,0,chamberLow],27,time,a.flame);
  if(o.effects&&m.effects.includes('spark')&&a.spark)g.line([[x,0,head-11],[x+3,0,head-15],[x-2,0,head-18],[x+2,0,head-21]],'#ffd960',2.5);
  if(o.effects&&m.effects.includes('coolant')){part('coolant-'+i,'缸'+(i+1)+' · 冷却水流','沿气缸外水套的教学流线，不计算传热或水泵工况。','fluid',[x,47,head*.6],c.water);const route=[];for(let j=0;j<=48;j++){const u=j/48;route.push([x+48*Math.cos(u*TAU*2),48*Math.sin(u*TAU*2),L-r+15+u*(r*2+10)]);}g.pipe(route,2.5,c.water,.22,6);flowParticles(g,route,time,{color:'#42cbea',count:32,radius:2,speed:.7});}
 }
 return g;
}
function jet3d(m,s,time,o){
 const g=new MeshScene(),c=colors,ex=o.explode||0,angle=s.angle*Math.PI/180,th=m.params.throttle;
 g.part('casing','分段机匣','外壳剖切仅切机匣；内部动静叶片保持完整。','housing',[0,44,0],c.blue,[0,ex*50,0]);g.tube([-180,0,0],[-135,0,0],65,59,c.blue,24,1,54,48);g.tube([-135,0,0],[-15,0,0],54,49,c.blue,24);g.tube([-15,0,0],[83,0,0],59,53,c.blue,24);g.tube([83,0,0],[134,0,0],52,47,c.blue,24);g.tube([134,0,0],[185,0,0],48,43,c.blue,24,1,31,26);
 g.part('shaft','压气机—涡轮主轴','单轴教学涡喷：涡轮与压气机由同一根轴联结。','moving',[0,0,0],c.steel);g.cylinder([-150,0,0],[160,0,0],8,c.steel,12);g.cylinder([-174,0,0],[-140,0,0],1,c.steel,16,1,16);g.cylinder([135,0,0],[181,0,0],15,c.steel,16,1,2);
 g.part('bearings','前后轴承','支撑主轴并传递载荷，外形简化。','fixed',[-145,0,0],c.copper);for(const x of [-145,128])g.tube([x-5,0,0],[x+5,0,0],15,9,c.copper,16);
 for(let i=0;i<5;i++){const x=-125+i*22,R=44-i*1.7;
  g.part('compressor-rotor-'+i,'压气机动叶 '+(i+1),'随主轴旋转的径向叶片列；不计算叶型气动性能。','moving',[x,R,0],c.blue,[0,0,ex*(i%2?12:-12)]);g.cylinder([x-3,0,0],[x+3,0,0],16,c.dark,12);for(let j=0;j<14;j++)blade(g,x,16,R,angle+j*TAU/14,8,5,c.blue);
  g.part('compressor-stator-'+i,'压气机静叶 '+(i+1),'静叶列不随轴转动；教学上对应整理气流方向的结构。','fixed',[x+11,0,R],c.teal);for(let j=0;j<14;j++)blade(g,x+11,20,R,j*TAU/14,6,-4,c.teal);
 }
 g.part('combustor','环形燃烧室与内外火焰筒','空心环形通道；火焰在火焰筒内部，没有温压或燃烧稳定性求解。','housing',[40,43,0],c.copper,[0,ex*28,ex*24]);g.tube([-8,0,0],[86,0,0],45,41,c.copper,24);g.tube([-8,0,0],[86,0,0],25,21,c.copper,20);
 g.part('injectors','燃油歧管与喷嘴','周向布置8个喷嘴；用于标记燃料进入环形燃烧区的位置。','fixed',[0,-35,0],c.red,[0,0,ex*18]);for(let j=0;j<8;j++){const a=j*TAU/8;g.cylinder(point(-8,34,a),point(7,34,a),2.2,c.red,6);g.tube(point(-9,34,a),point(-5,34,a),3.5,1,c.dark,6);}
 for(let i=0;i<2;i++){const x=96+i*22;
  g.part('turbine-stator-'+i,'涡轮导向静叶 '+(i+1),'在转子前的固定导向叶片。','fixed',[x-7,0,36],c.copper);for(let j=0;j<12;j++)blade(g,x-7,16,40,j*TAU/12,6,-5,c.copper);
  g.part('turbine-rotor-'+i,'涡轮动叶 '+(i+1),'高温气流经过转子；主轴把运动传到压气机。','moving',[x,40,0],c.copper,[0,0,ex*16]);g.cylinder([x-3,0,0],[x+3,0,0],16,c.dark,12);for(let j=0;j<12;j++)blade(g,x,16,40,angle+j*TAU/12,8,5,c.copper);
 }
 g.part('nozzle','收敛喷口与尾锥','喷口是三维空心锥段，不计算推力、马赫数或喷管压力。','housing',[175,28,0],c.steel,[ex*45,0,0]);g.tube([145,0,0],[188,0,0],44,39,c.steel,22,1,30,25);
 g.part('air','三维核心气流','沿进气道—压气机—环形燃烧室—涡轮—喷口的空间路径。','fluid',[0,33,0],c.water);
 if(o.effects&&m.effects.includes('airflow')&&th>0)for(let j=0;j<10;j++){const a=j*TAU/10,route=[point(-210,37,a),point(-140,33,a),point(-20,31,a+.4),point(70,33,a+.7),point(135,29,a+.9),point(215,14,a+1.1)];g.line(route,'#64c6e7',.6,.3);flowParticles(g,route,time,{color:j%2?'#65c8e5':'#bca5e7',count:20,radius:1.5,speed:.25+th*.8});}
 g.part('flames','环形燃烧火焰','8个空间火焰簇位于火焰筒环隙中；尾流为定性显示。','fluid',[35,34,0],c.red);
 if(o.effects&&m.effects.includes('flame')&&th>0)for(let j=0;j<8;j++){const a=j*TAU/8;flameVolume(g,point(5,33,a),point(62+th*14,33,a+.08),6,time,th);}
 return g;
}
function pump3d(m,s,time,o){
 const g=new MeshScene(),c=colors,ex=o.explode||0,a=s.angle*Math.PI/180;
 g.part('volute','渐扩蜗壳','沿叶轮外缘逐渐扩大的收集通道；形状为教学近似。','housing',[65,0,0],c.blue,[0,ex*35,0]);
 for(let j=0;j<28;j++){const t=j/28*TAU,q=(j+1)/28*TAU,ra=59+j*.6,rb=59+(j+1)*.6;const pts=[[ra*Math.cos(t),ra*Math.sin(t),-13],[rb*Math.cos(q),rb*Math.sin(q),-13],[rb*Math.cos(q),rb*Math.sin(q),13],[ra*Math.cos(t),ra*Math.sin(t),13]];g.face(pts,c.blue);g.face(pts.map(p=>[p[0]*.9,p[1]*.9,p[2]]),c.blue);}
 g.tube([-5,74,0],[100,74,0],17,12,c.blue,14);
 g.part('cover','泵盖与法兰','端盖、入口和紧固件；爆炸视图分离盖板以观察叶轮。','housing',[0,0,19],c.steel,[0,0,ex*70]);g.tube([0,0,14],[0,0,22],66,18,c.steel,24);g.tube([0,0,22],[0,0,77],24,18,c.blue,16);g.tube([0,0,75],[0,0,82],33,18,c.steel,16);
 for(let j=0;j<8;j++){const t=j*TAU/8;g.cylinder([56*Math.cos(t),56*Math.sin(t),19],[56*Math.cos(t),56*Math.sin(t),27],3,c.dark,6);}
 g.part('impeller','后弯叶轮与轮毂','7片后弯叶片随轴旋转；流线不用于预测泵性能。','moving',[30,0,0],c.teal);g.cylinder([0,0,-10],[0,0,-6],54,c.teal,24);g.cylinder([0,0,-7],[0,0,12],13,c.steel,14);
 for(let i=0;i<7;i++){const pts=[];for(let j=0;j<=10;j++){const u=j/10,r=14+u*37,t=a+i*TAU/7+u*.7;pts.push([r*Math.cos(t),r*Math.sin(t),0]);}for(let j=1;j<pts.length;j++){const p=pts[j-1],q=pts[j];g.face([[p[0],p[1],-6],[q[0],q[1],-6],[q[0],q[1],10],[p[0],p[1],10]],c.teal);}}
 g.part('shaft','泵轴与联轴器','轴把外部驱动传至叶轮；支承和机械密封位于叶轮后方。','moving',[0,0,-80],c.steel);g.cylinder([0,0,-115],[0,0,13],7,c.steel,12);g.cylinder([0,0,-116],[0,0,-99],15,c.dark,12);
 g.part('seal','机械密封动静环','简化的动静环配合位置；没有泄漏、摩擦或冷却计算。','fixed',[0,0,-28],c.copper,[0,0,-ex*20]);g.tube([0,0,-34],[0,0,-26],17,8,c.copper,16);g.tube([0,0,-25],[0,0,-19],17,8,c.dark,16);
 g.part('bearing','轴承与轴承座','泵轴支承；教学结构不包含滚动接触分析。','fixed',[0,0,-70],c.dark,[0,0,-ex*40]);g.tube([0,0,-82],[0,0,-60],23,9,c.dark,16);for(let j=0;j<8;j++){const t=j*TAU/8;g.cylinder([15*Math.cos(t),15*Math.sin(t),-78],[15*Math.cos(t),15*Math.sin(t),-65],3,c.copper,6);}
 g.part('water','入口—叶轮—蜗壳—出口水流','从轴向入口转入径向叶轮，再经蜗壳进入切向出口。水量和扬程未计算。','fluid',[0,0,50],c.water);
 if(o.effects&&m.effects.includes('flow')&&Math.abs(s.rpm)>0){const speed=Math.abs(s.rpm)/600;g.cylinder([0,0,78],[0,0,8],16,c.water,14,.14,16,false);for(let j=0;j<7;j++){const t=j*TAU/7,route=[[3*Math.cos(t),3*Math.sin(t),86],[7*Math.cos(t),7*Math.sin(t),9]];for(let k=0;k<=24;k++){const u=k/24,r=9+u*54,angle=t+u*1.6;route.push([r*Math.cos(angle),r*Math.sin(angle),3+Math.sin(u*Math.PI)*3]);}route.push([-5,74,3],[100,74,3]);g.pipe(route.slice(2),2.3,c.water,.18,5);flowParticles(g,route,time,{color:'#4ccbea',count:25,radius:1.8,speed:speed*.7});}}
 return g;
}
function wave3d(m,s,time,o,models){
 const g=new MeshScene(),c=colors,p=m.params,ex=o.explode||0;
 g.part('tank','透明水槽与水深','容器外形用于观察水面；线性波模型没有边界反射。','housing',[80,0,-25],c.blue);g.box([0,0,-35],[190,120,8],c.blue);for(const x of [-95,95])g.box([x,0,-8],[3,120,60],c.blue,.3);for(const y of [-60,60])g.box([0,y,-8],[190,3,60],c.blue,.3);
 g.part('water','三维水面与水体','三维网格表面来自一维线性波方程，竖向放大；没有自由表面流体求解。','fluid',[0,0,0],c.water,[0,0,ex*10]);
 const height=x=>o.effects&&m.effects.includes('water')?models.waveState(p,(x+90)/180*p.wavelength*2,time,s.drive).height*300:0,nx=36,ny=10;
 for(let i=0;i<nx;i++)for(let j=0;j<ny;j++){const x=-90+i*180/nx,y=-55+j*110/ny,xx=x+180/nx,yy=y+110/ny;g.face([[x,y,height(x)],[xx,y,height(xx)],[xx,yy,height(xx)],[x,yy,height(x)]],c.water,.58);}
 for(const y of [-55,55])for(let i=0;i<nx;i++){const x=-90+i*5;g.face([[x,y,-30],[x+5,y,-30],[x+5,y,height(x+5)],[x,y,height(x)]],c.water,.2);}
 // Fluid geometry is excluded from camera fitting: use fixed tank bounds.
 return g;
}
function motor3d(m,s,time,o){
 const g=new MeshScene(),c=colors,ex=o.explode||0,a=s.angle*Math.PI/180,I=s.motor.current;
 g.part('housing','电机壳与端盖','剖切外壳后可观察永磁体、绕组、换向器和轴承。','housing',[0,35,0],c.blue,[0,ex*35,0]);g.tube([-55,0,0],[55,0,0],38,33,c.blue,20);for(const x of [-58,58])g.tube([x-3,0,0],[x+3,0,0],38,8,c.steel,18);
 g.part('magnets','N/S永磁体','固定在机壳内的两极教学磁体。','fixed',[0,0,29],c.red);g.box([0,0,28],[82,28,8],c.red);g.box([0,0,-28],[82,28,8],c.blue);
 g.part('rotor','转子铁芯与输出轴','转子铁芯和轴同步旋转，转速来自电机稳态模型。','moving',[0,16,0],c.steel);g.cylinder([-85,0,0],[85,0,0],6,c.steel,12);g.cylinder([-35,0,0],[35,0,0],19,c.steel,16);for(let j=0;j<6;j++){const b=a+j*TAU/6,route=[point(-33,21,b),point(33,21,b),point(37,16,b+.3),point(-37,16,b+.3),point(-33,21,b)];g.pipe(route,2.3,c.copper,1,6);}
 g.part('commutator','分段换向器与碳刷','简化换向器与静止电刷的位置，未求解电弧或换向瞬态。','moving',[-44,12,0],c.copper);g.cylinder([-48,0,0],[-39,0,0],13,c.copper,12);for(const y of [-16,16])g.box([-44,y,0],[9,8,10],c.dark);
 g.part('bearing','前后轴承','支承转子轴，外形简化。','fixed',[58,0,0],c.copper);for(const x of [-58,58])g.tube([x-3,0,0],[x+3,0,0],11,6.5,c.copper,12);
 g.part('circuit','电源、开关与外部回路','电枢电阻包含在电机稳态方程内；不是通用电路求解器。','fixed',[-80,-65,0],c.dark);g.box([-80,-65,0],[24,36,23],c.dark);const route=[[-75,-65,12],[-75,-45,35],[-44,-20,12],[-44,20,12],[75,52,15],[75,-65,15],[-75,-65,12]];g.line(route,'#83a1b5',2);g.box([70,-60,15],[12,10,8],c.copper);
 g.part('electricity','电流与磁力线','电流粒子由实际稳态电流是否为零控制；磁场线为定性示意。','fluid',[0,0,0],c.copper);if(o.effects&&m.effects.includes('current')&&I>0)flowParticles(g,route,time,{color:'#efc44e',count:32,speed:Math.min(2,I),radius:1.8});if(o.effects&&m.effects.includes('field'))for(let j=0;j<5;j++){const x=-27+j*13;g.line([[x,0,25],[x,-20,14],[x,-20,-14],[x,0,-25]],'#b294d4',.8,.6);}
 return g;
}
function other3d(m,s,time,o,models){
 const g=new MeshScene(),c=colors;
 if(m.type==='assembly')for(const p of Object.values(s.assembly)){g.part(p.id,p.id,'自定义基本体与父子关节；给定运动，不解碰撞和受力。',p.joint==='fixed'?'fixed':'moving',p.position,({steel:c.steel,teal:c.teal,amber:c.copper,blue:c.blue})[p.color]);for(const f of p.faces)g.face(f.map(i=>p.vertices[i]));}
 else{const p=m.params,a=p.teeth_a,b=p.teeth_b,rad=90/(a+b),gear=(id,x,z,angle,color)=>{g.part(id,id==='gear-in'?'输入齿轮':'输出齿轮','简化齿形与轴；转速按齿数比计算。','moving',[x,0,0],color);g.cylinder([x,0,-6],[x,0,6],z*rad,color,Math.min(40,z*2));for(let j=0;j<z;j++){const t=j*TAU/z+angle;g.box([x+(z*rad+1)*Math.cos(t),(z*rad+1)*Math.sin(t),0],[3,3,12],color);}g.cylinder([x,0,-20],[x,0,20],5,c.steel,10);};gear('gear-in',-b*rad,a,s.inputAngle*Math.PI/180,c.blue);gear('gear-out',a*rad,b,s.angle*Math.PI/180,c.teal);}
 return g;
}
export function buildStructure(m,s,time,options,models){const o={explode:0,effects:true,...options};if(m.type==='four-stroke')return engine3d(m,s,time,o,models);if(m.type==='jet')return jet3d(m,s,time,o);if(m.type==='pump')return pump3d(m,s,time,o);if(m.type==='wave')return wave3d(m,s,time,o,models);if(m.type==='motor')return motor3d(m,s,time,o);return other3d(m,s,time,o,models);}
export function structureView(m,s,time,options,models){const mesh=buildStructure(m,s,time,options,models);return projectStructure(mesh,options);}
