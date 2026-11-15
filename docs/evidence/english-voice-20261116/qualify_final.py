"""Qualify the local TTS correction and repeat native adoption using unchanged policy."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from control.controller_pin import read
from modules.release_recovery.application import Applications

def main():
    native=json.loads((OUT/'native/result.json').read_text());assert native['passed'] and native['fixture_stopped']
    root=Path(native['root']);controller=Path(read(root)['controller']);port=native['port'];app=Applications(root)
    result={'passed':False,'steps':[]}
    def run(name,action,*args):
        p=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(controller/'apps/development/releases.py'),action,'--data-root',str(root),'--port',str(port),*map(str,args)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=240)
        (OUT/(name+'.txt')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,name
        value=json.loads(p.stdout);result['steps'].append({'name':name,'result':value});(OUT/'qualified.json').write_text(json.dumps(result,indent=2)+'\n');print(name,flush=True);return value
    archive=Path('E:/Jarvis/validation/english-voice-native-20261116/final.zip')
    final=run('final-build','build','--source',ROOT,'--archive',archive,'--version','0.1.12')['build'];run('final-stage','stage','--archive',archive)
    assert run('final-independent-validation','validate','--build',final,'--reviewed-source')['approval']
    path=root/'state/english-learning.sqlite3';before=hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        run('final-native-adopt','adopt','--build',final,'--expected-epoch',app.state()['epoch'])
        run('final-native-fallback','adopt','--build',native['fallback_build'],'--expected-epoch',app.state()['epoch'])
        run('final-native-return','adopt','--build',final,'--expected-epoch',app.state()['epoch'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    finally:run('final-native-stop','stop')
    result.update(passed=True,fixture_stopped=True,candidate_build=final,fallback_build=native['fallback_build'],archive=str(archive),same_learning_bytes=True)
    (OUT/'qualified.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
