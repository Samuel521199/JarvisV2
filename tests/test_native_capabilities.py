"""Dependency injection, integrity and portability regressions for native tools."""
import ast
from array import array
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sdk.blender_api import BlenderAPI, require_blender, using_blender
from sdk.native_programs import verify_program
from sdk.runtime_paths import project_path, optional_character_tool
from adapters.studio3d.reference_turret_front import deform_coordinates, triangle_audit

ROOT=Path(__file__).resolve().parents[1]


class NativeCapabilities(unittest.TestCase):
    def test_unbound_capability_and_normal_interpreter_cannot_load_native_consumer(self):
        with self.assertRaises(RuntimeError):require_blender()
        code='import sys;sys.path.insert(0,'+repr(str(ROOT))+');import adapters.studio3d.attachment_seat_worker'
        result=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('verified native worker bootstrap',result.stderr)

    def test_scoped_handle_and_exception_restore_no_native_auto_import(self):
        marker=SimpleNamespace(name='test-only-fake-handle')
        api=BlenderAPI(marker,marker,marker,marker,marker,marker)
        with self.assertRaisesRegex(ValueError,'sentinel'):
            with using_blender(api):
                self.assertIs(require_blender().bpy,marker)
                raise ValueError('sentinel')
        with self.assertRaises(RuntimeError):require_blender()
        self.assertNotIn('bpy',sys.modules)

    def test_registered_entry_integrity_and_unregistered_entry_denied(self):
        manifest=json.loads((ROOT/'modules/skills/studio3d/worker-programs.json').read_text())
        for entry in manifest['entries']:
            self.assertEqual(verify_program(ROOT,ROOT/entry),entry)
            tree=ast.parse((ROOT/entry).read_text(encoding='utf-8'))
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='install_runtime']
            self.assertEqual(len(calls),1,entry)
        with self.assertRaises(ValueError):verify_program(ROOT,ROOT/'apps/workbench/server.py')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'modules/skills/studio3d';p.mkdir(parents=True)
            (p/'worker-programs.json').write_text(json.dumps({'schema':1,'entries':['worker.py'],'sources':{'worker.py':'0'*64}}))
            (root/'worker.py').write_text('# changed')
            with self.assertRaisesRegex(ValueError,'source changed'):verify_program(root,root/'worker.py')

    def test_portable_data_assets_override_and_optional_tool_fails_on_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(sys,'argv',['native','--','--data-root',str(root/'data'),'--workspace-root',str(root/'assets')]),patch.dict(os.environ,{},clear=True):
                self.assertEqual(project_path('user-data/artifacts/a'),root/'data/artifacts/a')
                self.assertEqual(project_path('3DModels/a'),root/'assets/3DModels/a')
                with self.assertRaises(ValueError):project_path('../escape')
            bad=root/'character_tools.py';bad.write_text('raise RuntimeError("must not execute")')
            with patch.object(sys,'argv',['tool','--skill-tool',str(bad)]):
                with self.assertRaisesRegex(ValueError,'reviewed pin'):optional_character_tool()

    def test_shared_character_contract_retains_compatibility(self):
        from sdk import character_contract as shared
        from modules.skills.studio3d import character_contract as old
        self.assertIs(old.validate,shared.validate)
        self.assertEqual(old.parameters(),shared.parameters())

    def test_deformation_matches_independent_numpy_oracle_and_exact_unselected_bytes(self):
        # NumPy is a TEST oracle only; no runtime dependency remains.
        import numpy as np
        rng=np.random.default_rng(727)
        matrix=np.diag([1.65,1.65,1.65,1.]);matrix[:3,3]=[0,-.12,1.81]
        local=rng.uniform([-.6,-.7,-.1],[.6,.2,.5],(800,3)).astype(np.float32)
        world=local@matrix[:3,:3].T+matrix[:3,3];x,y,z=world.T
        def ease(v):
            t=np.clip(v,0,1);return t*t*(3-2*t)
        weight=ease((.71-np.abs(x))/.22)*ease((-.30-y)/.45)*ease((z-1.84)/.06)*(1-ease((z-2.37)/.05))
        changed=world.copy();changed[:,1]+=weight*(-.935-(-.899+.186*(z-1.96)))
        changed[:,2]+=.035*weight*ease((z-2.21)/.075)
        distances=np.linalg.norm(changed-world,axis=1);mask=distances>1e-7
        expected=local.copy();expected[mask]=((changed[mask]-matrix[:3,3])@np.linalg.inv(matrix[:3,:3]).T).astype(np.float32)
        out,selected,report=deform_coordinates(array('f',local.ravel()),matrix.tolist())
        actual=np.array(out).reshape(-1,3)
        self.assertTrue(np.array_equal(np.array(selected,dtype=bool),mask))
        np.testing.assert_array_equal(actual,expected)
        self.assertEqual(actual[~mask].tobytes(),local[~mask].tobytes())
        self.assertAlmostEqual(report['maximum_world_displacement'],float(distances.max()),places=12)
        self.assertEqual(report['moved_vertices'],int(mask.sum()))

    def test_deformation_guard_and_triangle_regression_fail_closed(self):
        matrix=[[1.65,0,0,0],[0,1.65,0,-.12],[0,0,1.65,1.81],[0,0,0,1]]
        with self.assertRaisesRegex(ValueError,'edit extent'):deform_coordinates(array('f',[10,10,10]),matrix)
        altered=[row[:] for row in matrix];altered[0][0]=1.7
        with self.assertRaisesRegex(ValueError,'frame'):deform_coordinates(array('f',[0,0,0]),altered)
        source=array('f',[0,0,0,1,0,0,0,1,0]);indices=array('i',[0,1,2])
        self.assertEqual(triangle_audit(source,source,bytearray([1,0,0]),indices)['affected_triangles'],1)
        for out in (array('f',[0,0,0,0,1,0,1,0,0]),array('f',[0,0,0,0,0,0,0,1,0])):
            with self.assertRaisesRegex(ValueError,'orientation/area'):triangle_audit(source,out,bytearray([1,1,1]),indices)
