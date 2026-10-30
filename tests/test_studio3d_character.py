import tempfile
import time
import unittest
import json
import subprocess
import sys
from pathlib import Path
from threading import Thread
from control.studio3d_lane import render_lane
from modules.context_knowledge.character_experience import methods, record, get_episode
from modules.context_knowledge.studio3d_experience import Studio3DExperience
from modules.skills.studio3d.character_contract import FAMILY, parameters, patch, validate
from modules.skills.studio3d.character_recipe import scene


class CharacterIsolation(unittest.TestCase):
    def test_character_contract_rejects_artillery_and_limits_changes(self):
        value={'schema':'jarvis.studio3d.character.v1','family':FAMILY,'asset_id':'character-test',
               'stage':'static_base','reference_sha256':{k:'a'*64 for k in ('front','rear','left','right')},'parameters':parameters()}
        validate(value)
        with self.assertRaises(ValueError):validate({**value,'family':'towed_artillery'})
        with self.assertRaises(ValueError):patch(parameters(),{'height':1.85})
        figure=scene(parameters());body=next(o for o in figure['objects'] if o['id']=='body-continuous')
        self.assertEqual(body['kind'],'mesh')
        self.assertTrue(any(o['id'].startswith('finger-') for o in figure['objects']))
        # Closed edge connectivity prevents the old detached joint blockout;
        # it does not certify deformation-ready topology.
        from collections import Counter
        faces=body['params']['faces']
        edges=Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
        self.assertTrue(edges)
        self.assertTrue(all(n==2 for n in edges.values()))

    def test_distinct_catalog_and_store_no_cross_promotion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'state').mkdir();rigid=Studio3DExperience(root)
            try:self.assertFalse(rigid.retrieve({'family':FAMILY,'symptoms':['floating_attachment']})['methods'])
            finally:rigid.close()
            with self.assertRaises(ValueError):methods('towed_artillery')
            result=record(root,family=FAMILY,asset_id='character-test',iteration='r0',evidence_sha256='a'*64,reviews={})
            self.assertFalse(result['automatic_promotion'])
            self.assertTrue((root/'state/studio3d-character-experience.sqlite3').exists())
            self.assertEqual(get_episode(root,family=FAMILY,asset_id='character-test',iteration='r0'),result)
            with self.assertRaises(ValueError):get_episode(root,family='towed_artillery',asset_id='character-test',iteration='r0')
            with self.assertRaises(KeyError):get_episode(root,family=FAMILY,asset_id='character-other',iteration='r0')
            record(root,family=FAMILY,asset_id='character-test',iteration='r0-audit',evidence_sha256='a'*64,reviews={'correction':'incorrect claim'})
            with self.assertRaisesRegex(ValueError,'audit correction'):get_episode(root,family=FAMILY,asset_id='character-test',iteration='r0')
            record(root,family=FAMILY,asset_id='character-test',iteration='clean',evidence_sha256='a'*64,reviews={})
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(root/'state/studio3d-character-experience.sqlite3')) as db, db:
                db.execute("UPDATE episodes SET body='{}' WHERE id='character-test:clean'")
            with self.assertRaisesRegex(ValueError,'content changed'):get_episode(root,family=FAMILY,asset_id='character-test',iteration='clean')

    def test_lane_waits_and_releases_between_workers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'state').mkdir();a=root/'artifacts/studio3d/a';b=root/'artifacts/studio3d-character/b'
            a.mkdir(parents=True);b.mkdir(parents=True);order=[]
            def second():
                with render_lane(b,timeout=3):order.append('second')
            with render_lane(a,timeout=3):
                thread=Thread(target=second);thread.start();time.sleep(.35)
                self.assertEqual(order,[]);order.append('first')
            thread.join(3);self.assertEqual(order,['first','second'])
            self.assertTrue((b/'resource-lane.json').is_file())

    def test_lane_serializes_separate_processes_and_recovers_after_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'state').mkdir();a=root/'artifacts/studio3d/a';b=root/'artifacts/studio3d-character/b'
            a.mkdir(parents=True);b.mkdir(parents=True)
            code=('import sys,time; from control.studio3d_lane import render_lane; '
                  'p=sys.argv[1]; hold=float(sys.argv[2]); '
                  'lane=render_lane(p,timeout=8); lane.__enter__(); '
                  'time.sleep(hold); lane.__exit__(None,None,None)')
            flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            first=subprocess.Popen([sys.executable,'-c',code,str(a),'1'],creationflags=flags)
            second=None
            try:
                for _ in range(100):
                    if (a/'resource-lane.json').exists():break
                    time.sleep(.02)
                self.assertTrue((a/'resource-lane.json').exists())
                second=subprocess.Popen([sys.executable,'-c',code,str(b),'0'],creationflags=flags)
                self.assertEqual(first.wait(timeout=8),0);self.assertEqual(second.wait(timeout=8),0)
                wait=json.loads((b/'resource-lane.json').read_text())['queue_seconds']
                self.assertGreater(wait,.4)
            finally:
                if first.poll() is None:first.kill();first.wait()
                if second and second.poll() is None:second.kill();second.wait()

if __name__=='__main__':unittest.main()
