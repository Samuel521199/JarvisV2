"""Wait for one managed host and retain its exit status; never restart work."""
from pathlib import Path
import json,os,subprocess,sys,time

def main():
    args=sys.argv[1:];root=Path(args[args.index('--data-root')+1]).resolve()
    epoch=args[args.index('--application-epoch')+1]
    logs=root/'deployment/logs';logs.mkdir(parents=True,exist_ok=True)
    path=logs/(epoch+'.lifecycle.json')
    record={'schema':1,'supervisor_pid':os.getpid(),'started':time.time(),'host_pid':None,'exit_code':None,'finished':None,'automatic_restart':False}
    def save():
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
    save()
    try:
        process=subprocess.Popen([sys.executable,'-X','faulthandler','-I','-B',str(Path(__file__).with_name('server.py')),*args],stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        record['host_pid']=process.pid;save();record['exit_code']=process.wait()
    except BaseException as error:
        record['error_type']=type(error).__name__;raise
    finally:
        record['finished']=time.time();save()
    return record['exit_code']
if __name__=='__main__':sys.exit(main())
