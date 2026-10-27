"""First-party bounded numerical models; SI inputs/outputs, no expressions."""
import math

def rk4(f,y,dt):
    a=f(y);b=f([v+dt*k/2 for v,k in zip(y,a)]);c=f([v+dt*k/2 for v,k in zip(y,b)]);d=f([v+dt*k for v,k in zip(y,c)])
    return [v+dt*(aa+2*bb+2*cc+dd)/6 for v,aa,bb,cc,dd in zip(y,a,b,c,d)]

def motor_pump(p):
    V,R,L,K,J,b,c=[p[k] for k in ('voltage','resistance','inductance','constant','inertia','friction','pump_coefficient')]
    n=math.ceil(p['duration']/min(.001,.3*L/R,.3*J/(b+K+1e-9)))
    if n>200000:raise ValueError('Motor integration budget exceeded')
    dt=p['duration']/n;y=[0.,0.,0.,0.];rows=[];stride=max(1,n//300)
    def rhs(y):
        i,w=y[:2];torque=c*w*abs(w)
        return [(V-R*i-K*w)/L,(K*i-b*w-torque)/J,V*i,R*i*i+b*w*w+torque*w]
    for k in range(n+1):
        if k%stride==0 or k==n:rows.append([k*dt,y[0],y[1]*60/(2*math.pi),c*y[1]*abs(y[1])])
        if k<n:y=rk4(rhs,y,dt)
    stored=.5*L*y[0]**2+.5*J*y[1]**2;residual=y[2]-y[3]-stored
    return {'kind':'motor-pump','title':'电机—泵负载瞬态','columns':['time_s','current_A','speed_rpm','pump_torque_Nm'],'rows':rows,'summary':{'final_current_A':y[0],'final_speed_rpm':y[1]*60/(2*math.pi),'energy_residual_J':residual,'relative_energy_error':abs(residual)/max(1,abs(y[2])),'steps':n,'time_step_s':dt},'limits':'集总直流电机 L·di/dt=V−Ri−Kω，J·dω/dt=Ki−bω−cω|ω|；泵负载系数为用户给定，不根据叶轮外观预测扬程/流量。'}

def otto(p):
    r,g,T,P,q,d=[p[k] for k in ('compression','gamma','temperature','pressure','heat_input','displacement_cc')]
    R=287.05;cv=R/(g-1);v2=d*1e-6/(r-1);v1=r*v2;mass=P*v1/(R*T)
    t2=T*r**(g-1);t3=t2+q/cv;t4=t3/r**(g-1);rows=[]
    for stage in range(4):
        for j in range(41):
            u=j/40
            if stage==0:v=v1+(v2-v1)*u;t=T*(v1/v)**(g-1)
            elif stage==1:v=v2;t=t2+(t3-t2)*u
            elif stage==2:v=v2+(v1-v2)*u;t=t3*(v2/v)**(g-1)
            else:v=v1;t=t4+(T-t4)*u
            rows.append([v*1e6,mass*R*t/v,t,stage])
    efficiency=1-1/r**(g-1);work=mass*cv*((t3-t4)-(t2-T))
    return {'kind':'otto','title':'理想 Otto 热力循环','columns':['volume_cc','pressure_Pa','temperature_K','stage'],'rows':rows,'summary':{'efficiency':efficiency,'cycle_work_J':work,'heat_input_J':mass*q,'mass_kg':mass,'peak_temperature_K':t3,'energy_residual_J':work-mass*q*efficiency},'limits':'定比热理想空气标准循环，闭系统等容加热/冷却与绝热压缩/膨胀；不是实际发动机燃烧、功率或排放预测。'}

def channel(p):
    H,L,mu,rho,dp,n=[p[k] for k in ('height','length','viscosity','density','pressure_drop','cells')];dy=H/n
    # Tridiagonal finite-difference solution of mu*u_yy = -dp/L; no-slip walls.
    a=[-1.]*(n-1);b=[2.]*(n-1);c=[-1.]*(n-1);d=[dp/L/mu*dy*dy]*(n-1)
    for j in range(1,n-1):w=a[j]/b[j-1];b[j]-=w*c[j-1];d[j]-=w*d[j-1]
    u=[0.]*(n-1);u[-1]=d[-1]/b[-1]
    for j in range(n-3,-1,-1):u[j]=(d[j]-c[j]*u[j+1])/b[j]
    u=[0.]+u+[0.];exact=lambda y:dp/(2*mu*L)*y*(H-y);speed=dp*H*H/(12*mu*L);error=max(abs(u[j]-exact(j*dy)) for j in range(n+1))
    return {'kind':'channel','title':'充分发展层流通道','columns':['y_m','velocity_m_s','analytical_m_s'],'rows':[[j*dy,u[j],exact(j*dy)] for j in range(n+1)],'field':{'x':[L*i/20 for i in range(21)],'y':[j*dy for j in range(n+1)],'velocity':u,'pressure':[dp*(1-i/20) for i in range(21)]},'summary':{'reynolds_hydraulic':rho*speed*2*H/mu,'max_velocity_error_m_s':error,'flow_per_width_m2_s':sum(u)*dy,'analytical_flow_per_width_m2_s':speed*H,'relative_flow_error':abs(sum(u)*dy-speed*H)/(speed*H),'divergence':0,'grid_cells':n},'limits':'充分发展、稳态、平行板不可压层流的横向有限差分解；压强沿程线性，横向速度为零。二维场由这一受限解展开，不含障碍物、湍流或任意二维 CFD。'}

def shallow_water(p):
    n=p['cells'];length=p['length'];dx=length/n;g=9.81;x=[(i+.5)*dx for i in range(n)];h=[p['depth']+p['amplitude']*math.exp(-((z-length/2)/(length*.08))**2) for z in x];q=[0.]*n;t=0;frames=[];mass0=sum(h)*dx;steps=0;next_frame=0
    while True:
        if t>=next_frame or t>=p['duration']:
            frames.append({'time':t,'height':h[:],'velocity':[qq/hh for hh,qq in zip(h,q)]});next_frame=t+p['duration']/40
        if t>=p['duration']:break
        speed=max(abs(qq/hh)+math.sqrt(g*hh) for hh,qq in zip(h,q));dt=min(.4*dx/speed,p['duration']-t)
        hh=[h[0]]+h+[h[-1]];qq=[-q[0]]+q+[-q[-1]];flux=[]
        for i in range(n+1):
            hl,hr,ql,qr=hh[i],hh[i+1],qq[i],qq[i+1];ul,ur=ql/hl,qr/hr;s=max(abs(ul)+math.sqrt(g*hl),abs(ur)+math.sqrt(g*hr))
            flux.append([.5*(ql+qr)-.5*s*(hr-hl),.5*(ql*ul+.5*g*hl*hl+qr*ur+.5*g*hr*hr)-.5*s*(qr-ql)])
        h=[h[i]-dt/dx*(flux[i+1][0]-flux[i][0]) for i in range(n)];q=[q[i]-dt/dx*(flux[i+1][1]-flux[i][1]) for i in range(n)]
        if min(h)<=0:raise ValueError('Wet-domain solver lost positivity')
        t+=dt;steps+=1
        if steps>10000:raise ValueError('Shallow-water integration budget exceeded')
    return {'kind':'shallow-water','title':'守恒浅水波传播','columns':['x_m','initial_depth_m','final_depth_m'],'rows':[[z,frames[0]['height'][i],h[i]] for i,z in enumerate(x)],'frames':frames,'summary':{'initial_mass_per_width_m2':mass0,'final_mass_per_width_m2':sum(h)*dx,'relative_mass_error':abs(sum(h)*dx-mass0)/mass0,'small_signal_wave_speed_m_s':math.sqrt(g*p['depth']),'steps':steps,'min_depth_m':min(h)},'limits':'一维非线性浅水方程、Rusanov 有限体积、反射壁边界、始终湿域；有数值耗散，不含翻卷、飞溅、空化或通用三维液体。'}

def pendulum(p):
    theta=math.radians(p['angle_deg']);y=[theta,0.,0.];n=math.ceil(p['duration']/.002);dt=p['duration']/n;rows=[]
    def f(y):return [y[1],-9.81/p['length']*math.sin(y[0])-p['damping']*y[1],p['damping']*p['length']**2*y[1]**2]
    energy0=9.81*p['length']*(1-math.cos(theta))
    for i in range(n+1):
        if i%max(1,n//300)==0 or i==n:rows.append([i*dt,math.degrees(y[0]),y[1]])
        if i<n:y=rk4(f,y,dt)
    energy=.5*(p['length']*y[1])**2+9.81*p['length']*(1-math.cos(y[0]))
    return {'kind':'pendulum','title':'受重力和阻尼的刚性单摆','columns':['time_s','angle_deg','angular_speed_rad_s'],'rows':rows,'summary':{'small_angle_period_s':2*math.pi*math.sqrt(p['length']/9.81),'energy_residual_per_kg_J':energy+y[2]-energy0,'time_step_s':dt},'limits':'限定单自由度刚性点质量单摆，非通用刚体接触或装配动力学；周期公式仅小角近似。'}

def fourbar(p):
    ground,crank,coupler,follower=[p[k] for k in ('ground','crank','coupler','follower')];rows=[];poses=[];unreachable=0;residual=0
    for deg in range(0,361,2):
        a=math.radians(deg);B=[crank*math.cos(a),crank*math.sin(a)];delta=[ground-B[0],-B[1]];d=math.hypot(*delta)
        if d<1e-9 or d>coupler+follower+1e-8 or d<abs(coupler-follower)-1e-8:unreachable+=1;continue
        x=(coupler**2-follower**2+d*d)/(2*d);h=math.sqrt(max(0,coupler**2-x*x));u=[v/d for v in delta];C=[B[0]+x*u[0]-h*u[1],B[1]+x*u[1]+h*u[0]]
        residual=max(residual,abs(math.dist(B,C)-coupler),abs(math.dist(C,[ground,0])-follower));rows.append([deg,C[0],C[1]]);poses.append({'angle_deg':deg,'points':[[0,0],B,C,[ground,0]]})
    return {'kind':'fourbar','title':'平面四杆闭链约束','columns':['input_angle_deg','coupler_x_mm','coupler_y_mm'],'rows':rows,'poses':poses,'summary':{'unreachable_samples':unreachable,'closure_residual_mm':residual,'valid_samples':len(poses)},'limits':'限定平面四杆，两圆交点选取同一开式分支；部分角度不可装配会记录不可达，不保证穿越奇异位形时的分支连续性，不含接触或受力。'}

def arm_ik(p):
    L1,L2,x,y=[p[k] for k in ('upper','lower','target_x','target_y')];c=(x*x+y*y-L1*L1-L2*L2)/(2*L1*L2);rows=[];poses=[];error=0
    if math.hypot(x,y)<1e-10 and abs(L1-L2)<1e-10:
        return {'kind':'arm-ik','title':'二连杆机械臂逆运动学','columns':['branch','shoulder_deg','elbow_deg'],'rows':[],'poses':[],'summary':{'reachable':True,'solutions':None,'solution_family':'infinite','target_error_mm':None},'limits':'等长二连杆完全折叠到原点是退化无穷多解；未伪造唯一姿态，不包含关节限位/碰撞或载荷。'}
    if -1-1e-10<=c<=1+1e-10:
        for sign in ([1] if abs(abs(c)-1)<1e-10 else [1,-1]):
            q2=sign*math.acos(max(-1,min(1,c)));q1=math.atan2(y,x)-math.atan2(L2*math.sin(q2),L1+L2*math.cos(q2));B=[L1*math.cos(q1),L1*math.sin(q1)];C=[B[0]+L2*math.cos(q1+q2),B[1]+L2*math.sin(q1+q2)];error=max(error,math.dist(C,[x,y]));rows.append([sign,math.degrees(q1),math.degrees(q2)]);poses.append({'points':[[0,0],B,C]})
    return {'kind':'arm-ik','title':'二连杆机械臂逆运动学','columns':['branch','shoulder_deg','elbow_deg'],'rows':rows,'poses':poses,'summary':{'reachable':bool(poses),'solutions':len(poses),'target_error_mm':error if poses else None},'limits':'限定平面二连杆解析逆解；保留肘上/肘下分支，不包含关节限位、障碍物、负载或通用六轴机械臂。不可达目标不伪造姿态。'}

SOLVERS={'motor-pump':motor_pump,'otto':otto,'channel':channel,'shallow-water':shallow_water,'pendulum':pendulum,'fourbar':fourbar,'arm-ik':arm_ik}
def solve(experiments,optional=None):
    solvers={**SOLVERS,**(optional or {})}
    return [solvers[e['kind']](e['params']) for e in experiments]
