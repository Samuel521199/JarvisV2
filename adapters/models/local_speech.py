"""Windows installed voice synthesis; bounded stdin text, no network or download."""
import base64,io,json,os,re,tempfile,time,wave
from pathlib import Path
from control.worker.process import OwnedProcess
from sdk.protocol import CoreError

SCRIPT=r'''$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Speech
$request=[Console]::In.ReadToEnd() | ConvertFrom-Json
$synth=New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
 $synth.Rate=-2
 $memory=New-Object System.IO.MemoryStream
 $format=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
 $synth.SetOutputToAudioStream($memory,$format)
 foreach($part in $request.parts){
  $lang=[string]$part.language
  $voices=@($synth.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Culture.Name -like ($lang+'-*')})
  if($voices.Count -lt 1){throw ('installed_voice_unavailable_'+$lang)}
  $synth.SelectVoice($voices[0].VoiceInfo.Name);$synth.Speak([string]$part.text)
 }
 [Console]::Out.Write([Convert]::ToBase64String($memory.ToArray()))
} finally {$synth.Dispose()}
'''

def synthesize(text,*,language='en',checkpoint=lambda:None,work_dir=None):
    if os.name!='nt' or language not in ('en','zh','auto') or not isinstance(text,str) or not text.strip() or len(text)>500:raise CoreError('english_tts','Expected a short expression and supported language on Windows')
    parts=[]
    for chunk in (re.findall(r'[\u3400-\u9fff]+|[^\u3400-\u9fff]+',text) if language=='auto' else [text]):
        lang=('zh' if re.search(r'[\u3400-\u9fff]',chunk) else 'en') if language=='auto' else language
        if language=='auto' and parts and not re.search(r'[A-Za-z0-9\u3400-\u9fff]',chunk):parts[-1]['text']+=chunk
        else:parts.append({'text':chunk,'language':lang})
    encoded=base64.b64encode(SCRIPT.encode('utf-16le')).decode()
    if work_dir:Path(work_dir).mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='speech-tts-',dir=work_dir) as folder:
        env={k:os.environ[k] for k in ('SystemRoot','WINDIR') if k in os.environ};env.update(TEMP=folder,TMP=folder)
        with tempfile.TemporaryFile(dir=folder) as output,tempfile.TemporaryFile(dir=folder) as error:
            executable=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
            process=OwnedProcess([str(executable),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],stdout=output,stderr=error,env=env,cwd=folder,input=json.dumps({'parts':parts}).encode(),processes=1,cpu_seconds=15,memory_bytes=512*1024**2,checkpoint=checkpoint)
            try:
                deadline=time.monotonic()+35
                while process.poll() is None:
                    checkpoint()
                    if time.monotonic()>deadline or output.tell()>2560200 or error.tell()>8192:raise CoreError('english_tts','Local speech exceeded its bound')
                    time.sleep(.05)
                checkpoint()
                if process.returncode:raise CoreError('english_tts','Installed voice failed; check target language availability')
                output.seek(0)
                try:raw=base64.b64decode(output.read(2560201),validate=True)
                except ValueError:raise CoreError('english_tts','Invalid local voice output') from None
            finally:process.close()
    if not 100<len(raw)<=1920000 or len(raw)%2:raise CoreError('english_tts','Invalid local speech output')
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setparams((1,2,16000,len(raw)//2,'NONE','not compressed'));audio.writeframes(raw)
    return base64.b64encode(output.getvalue()).decode()
