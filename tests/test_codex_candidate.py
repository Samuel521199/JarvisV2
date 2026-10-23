"""External candidate protocol, shutdown and privilege boundaries without account access."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_development as base
from adapters.models import codex_cli as cli
from sdk.protocol import CoreError, canonical, contract, read_json


def events(value=None):
    return '\n'.join(canonical(e) for e in [
        {'type':'turn.started'},
        {'type':'item.completed','item':{'type':'agent_message','text':canonical(value or base.candidate())}},
        {'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':20}}]).encode()


class CodexCandidate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.binary=self.root/'codex.exe';self.binary.write_bytes(b'test binary')
        self.config={'executable':str(self.binary),'executable_sha256':hashlib.sha256(b'test binary').hexdigest(),
                     'model':'test-model','parameters':{'reasoning':'medium'},'max_prompt_bytes':50000,'timeout_seconds':1}
        self.model=cli.CodexModel(self.config,self.root)
        self.prompt=canonical({'output_schema':read_json(base.ROOT/'contracts/schemas/code-candidate.v1.json'),'goal':'uppercase'})
    def tearDown(self):self.temp.cleanup()

    def test_success_and_usage_are_candidate_receipt_only(self):
        result=cli.parse_events(events(),0);contract('code-candidate',result['value'])
        self.assertEqual(result['status'],'SUCCEEDED');self.assertEqual(result['usage']['output_tokens'],20)
        self.assertEqual(result['usage']['total_tokens'],32)
        self.assertEqual(result['usage']['prompt_tokens'],12)
        for kind in ('command_execution','file_change','mcp_tool_call','web_search','collab_tool_call'):
            forbidden=canonical({'type':'item.started','item':{'type':kind}}).encode()+b'\n'+events()
            self.assertEqual(cli.parse_events(forbidden,0)['code'],'codex_tool_event')

    def test_known_rejection_and_unknown_execution_are_distinct(self):
        self.assertEqual(cli.parse_events(b'',1)['status'],'REJECTED')
        self.assertEqual(cli.parse_events(b'{"type":"turn.started"}',1)['status'],'UNKNOWN')
        raw=events().replace(canonical(base.candidate()).encode(),b'not-json')
        # An agent_message with non-JSON text cannot become a package.
        raw=b'{"type":"item.completed","item":{"type":"agent_message","text":"not-json"}}\n{"type":"turn.completed"}'
        self.assertEqual(cli.parse_events(raw,0)['status'],'INVALID')

    def test_no_tools_user_configuration_or_hooks(self):
        args=cli.arguments(self.config,self.root,self.root/'schema.json')
        for flag in ('--ignore-user-config','--ignore-rules','--strict-config','--ephemeral','read-only','approval_policy="never"','mcp_servers={}'):self.assertIn(flag,args)
        for feature in cli.DISABLED:self.assertIn(['--disable',feature],[args[i:i+2] for i in range(len(args)-1)])
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)

    def test_binary_change_and_non_candidate_prompt_rejected_before_start(self):
        with patch.object(cli.subprocess,'Popen') as process:
            self.assertEqual(self.model.generate(canonical({'output_schema':{}}))['code'],'codex_candidate_only')
            self.binary.write_bytes(b'changed');self.assertEqual(self.model.generate(self.prompt)['code'],'codex_binary_changed')
            process.assert_not_called()

    def test_local_version_including_prerelease_is_pinned(self):
        with patch.object(cli.shutil,'which',return_value=str(self.binary)),patch.object(cli.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'codex-cli 0.163.0-alpha.11.1\n')):
            result=cli.discover();self.assertTrue(result['available']);self.assertEqual(result['sha256'],self.config['executable_sha256'])
        with patch.object(cli.shutil,'which',return_value=None):self.assertFalse(cli.discover()['available'])

    def process(self,*args,**kwargs):
        self.seen=kwargs
        class Process:
            pid=424242;returncode=None
            def communicate(inner,payload=None,timeout=None):
                if timeout is None:inner.returncode=0;return
                raise subprocess.TimeoutExpired('test',timeout)
            def poll(inner):return inner.returncode
            def kill(inner):inner.returncode=-1
        return Process()

    def test_timeout_kills_owned_process_and_cleans_workspace(self):
        with patch.object(cli.subprocess,'Popen',side_effect=self.process),patch.object(cli.subprocess,'run') as kill,patch.object(cli.time,'monotonic',side_effect=[0,2]):
            result=self.model.generate(self.prompt)
        self.assertEqual(result['code'],'codex_timeout');self.assertEqual(result['status'],'UNKNOWN')
        if cli.os.name=='nt':self.assertEqual(kill.call_args.args[0][1:4],['/PID','424242','/T'])
        self.assertEqual(list((self.root/'temp').iterdir()),[])
        self.assertNotIn('OPENAI_API_KEY',self.seen['env']);self.assertNotIn('shell',self.seen)

    def test_cancellation_stops_process_and_cleans_workspace(self):
        count=0
        def checkpoint():
            nonlocal count
            count+=1
            if count>1:raise CoreError('cancelled','cancelled')
        with patch.object(cli.subprocess,'Popen',side_effect=self.process),patch.object(cli.subprocess,'run') as kill:
            with self.assertRaises(CoreError):self.model.generate(self.prompt,checkpoint)
        if cli.os.name=='nt':kill.assert_called_once()
        self.assertEqual(list((self.root/'temp').iterdir()),[])


if __name__=='__main__':unittest.main()
