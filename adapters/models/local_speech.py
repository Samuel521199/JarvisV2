"""Windows installed voice synthesis; bounded stdin text, no network or download."""
import base64,io,json,os,subprocess,wave
from sdk.protocol import CoreError

SCRIPT=r'''$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Speech
$request=[Console]::In.ReadToEnd() | ConvertFrom-Json
$synth=New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
 $voices=@($synth.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*'})
 if($voices.Count -lt 1){throw 'english_voice_unavailable'}
 $synth.SelectVoice($voices[0].VoiceInfo.Name);$synth.Rate=-2
 $memory=New-Object System.IO.MemoryStream
 $format=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
 $synth.SetOutputToAudioStream($memory,$format);$synth.Speak([string]$request.text)
 [Console]::Out.Write([Convert]::ToBase64String($memory.ToArray()))
} finally {$synth.Dispose()}
'''

def synthesize(text):
    if os.name!='nt' or not isinstance(text,str) or not text.strip() or len(text)>500:raise CoreError('english_tts','Expected a short English expression on Windows')
    encoded=base64.b64encode(SCRIPT.encode('utf-16le')).decode()
    try:
        process=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],input=json.dumps({'text':text}).encode(),capture_output=True,timeout=35,creationflags=subprocess.CREATE_NO_WINDOW)
        if process.returncode or len(process.stdout)>2560200:raise CoreError('english_tts','Installed English voice failed or output exceeded bound')
        raw=base64.b64decode(process.stdout,validate=True)
    except (OSError,ValueError,subprocess.TimeoutExpired):raise CoreError('english_tts','Local English synthesis did not complete') from None
    if not 100<len(raw)<=1920000 or len(raw)%2:raise CoreError('english_tts','Invalid local speech output')
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setparams((1,2,16000,len(raw)//2,'NONE','not compressed'));audio.writeframes(raw)
    return base64.b64encode(output.getvalue()).decode()
