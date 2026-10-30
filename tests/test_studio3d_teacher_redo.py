import copy
import unittest
from test_studio3d_demonstration import contract
from test_studio3d_radial_profile import action
from modules.skills.studio3d.teacher_redo import validate_plan


class TeacherRedoTests(unittest.TestCase):
    def inputs(self):
        c=contract();c['actions']=[action()]
        return c,{'decision':'execute','actions':copy.deepcopy(c['actions']),'lesson_used':['profile lesson'],'checks':['actual render'],'limits':['local only']}

    def test_classifies_replay_and_preserves_jarvis_choices(self):
        c,r=self.inputs();out,a=validate_plan(r,c);self.assertEqual(a['mode'],'EXACT_PARAMETER_REPLAY')
        r['actions'][0]['amplitude']=.02;out,a=validate_plan(r,c)
        self.assertEqual(out['actions'],r['actions']);self.assertEqual(out['author'],'Jarvis');self.assertEqual(c['author'],'Codex')
        self.assertEqual(a['mode'],'JARVIS_PARAMETER_SELECTION');self.assertFalse(a['independent_success'])

    def test_rejects_unrequested_geometry_or_code(self):
        for key,value in [('center',[1,1,1]),('lobes',12),('inner',.21),('amplitude',.035),('tool','execute_python')]:
            c,r=self.inputs();r['actions'][0][key]=value
            with self.assertRaises(ValueError):validate_plan(r,c)

    def test_tool_gap_not_filled_in_by_host(self):
        c,r=self.inputs();r.update(decision='tool_gap',actions=[])
        out,a=validate_plan(r,c);self.assertIsNone(out);self.assertEqual(a['mode'],'DECLINED_TOOL_GAP')
        r['actions']=[action()]
        with self.assertRaises(ValueError):validate_plan(r,c)


if __name__=='__main__':unittest.main()
