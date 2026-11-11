"""Five-minute observed bounds on one owned Host; no real user data or cloud."""
from pathlib import Path
import ctypes,json,shutil,socket,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from host.core import Core
from host import goals,standing_work
from control.application_runtime import LocalApprovals,publish
from adapters.application_host import WorkbenchProcess
from test_development import specification,candidate
from test_preferences_dialogue import fixture
from test_standing_work import checks,config


def run(work):
    work.mkdir(parents=True,exist_ok=False);root=work/'data';core=Core.initialize(root);core.preferences.install(fixture(),{})
    shutil.copytree(ROOT/'user-data/worker-runtime',root/'worker-runtime');spec=specification('standing-idle')
    package=core.packages.stage(candidate('def run(text):\n    return text.upper()\n'),spec)
    assert core.packages.verify(package)['passed'];core.packages.activate(package,0);core.close()
    request={'request_id':'idle-source-request','goal':'合成固定文字','input_text':'hello','provider':'openai','model':'test-model','reasoning':'default'}
    source=goals.command(root,{'action':'create','request':request});detail=goals.command(root,{'action':'detail','id':source['id']})
    goals.command(root,{'action':'edit','id':source['id'],'revision':detail['plan']['revision'],'proposal':{'schema':'jarvis.goal-plan.v1','summary':'固定文字','input_text':'hello','steps':[{'title':'转换','capability':spec['capability'],'source':'input','expected':'HELLO'}],'questions':[]}})
    row=standing_work.command(root,{'action':'create','request_id':'idle-standing-create','title':'未来安排资源验收','plans':[{'goal_id':source['id'],'acceptance':checks('HELLO')}],'policy':config(start_at='2099-01-01T09:00:00+08:00')})
    standing_work.command(root,{'action':'approve','request_id':'idle-standing-approve','id':row['id'],'revision':row['revision']})
    LocalApprovals(root).initialize()
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    selected={'build':'e'*64,'slot':'A','epoch':1};driver=WorkbenchProcess(root,port);publish(root,selected['build'],1,'starting')
    with (work/'host.log').open('wb') as log:
        p=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(Path(__file__).with_name('runtime_closure.py')),'host','--data-root',str(root),'--port',str(port),'--application-build',selected['build'],'--application-epoch','1'],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    driver.processes[1]=p;report={'passed':False,'seconds_target':300,'scope':'one active future mandate; current Windows PC; concurrent tests; not 8 GiB/long-term proof','thresholds':{'peak_rss_mib':512,'rss_growth_mib':128,'health_p95_seconds':1},'samples':[]}
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),*[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]]
    memory=ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo;memory.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong];memory.restype=ctypes.c_int
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);times=kernel.GetProcessTimes;times.argtypes=[ctypes.c_void_p,*([ctypes.POINTER(ctypes.c_ulonglong)]*4)];times.restype=ctypes.c_int
    def sample():
        c=Counters();c.cb=ctypes.sizeof(c);assert memory(int(p._handle),ctypes.byref(c),c.cb)
        a,b,k,u=[ctypes.c_ulonglong() for _ in range(4)];assert times(int(p._handle),*[ctypes.byref(x) for x in (a,b,k,u)])
        t=time.monotonic();driver.health(selected,1);latency=time.monotonic()-t
        return {'at':time.monotonic(),'rss_mib':c.WorkingSetSize/1048576,'cpu_seconds':(k.value+u.value)/10000000,'health_seconds':latency}
    try:
        driver.health(selected,1);publish(root,selected['build'],1,'active');driver.activate(selected,1);start=time.monotonic();first=sample();report['samples'].append(first)
        while time.monotonic()-start<300:
            time.sleep(min(5,300-(time.monotonic()-start)))
            report['samples'].append(sample())
        final=report['samples'][-1];latencies=sorted(x['health_seconds'] for x in report['samples']);peak=max(x['rss_mib'] for x in report['samples'])
        report['measured']={'seconds':final['at']-first['at'],'peak_rss_mib':peak,'rss_growth_mib':final['rss_mib']-first['rss_mib'],'cpu_one_core_percent':100*(final['cpu_seconds']-first['cpu_seconds'])/(final['at']-first['at']),'health_p95_seconds':latencies[int(.95*(len(latencies)-1))]}
        core=Core(root)
        try:assert not core.db.all('SELECT * FROM tasks') and not core.db.all('SELECT * FROM model_calls')
        finally:core.close()
        m=report['measured'];assert m['seconds']>=300 and peak<512 and m['rss_growth_mib']<128 and m['health_p95_seconds']<1
        report['passed']=True
    finally:
        publish(root,selected['build'],1,'draining');driver.drain(selected,1);driver.stop(selected,1)
        report['owned_host_stopped']=p.poll() is not None;(work/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}))


if __name__=='__main__':run(Path(sys.argv[1]).resolve())
