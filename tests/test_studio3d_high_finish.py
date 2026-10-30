import copy
import unittest
from modules.skills.studio3d.high_finish import validate,uv_independent_shader


class HighFinishContract(unittest.TestCase):
    def config(self):
        return {'texture_size':512,'groups':[{'id':'body','members':['body'],'parent':None,'pivot':[0,0,0],'motion':'fixed'},
            {'id':'wheel','members':['wheel'],'parent':'body','pivot':[0,1,1],'motion':'visual_rotation'}]}

    def test_valid_separate_motion_ownership(self):
        validate(self.config(),['body','wheel'])

    def test_missing_duplicate_or_unknown_members_rejected(self):
        for members in ([],['body'],['wheel','wheel'],['wheel','unknown']):
            c=self.config();c['groups'][1]['members']=members
            with self.assertRaises(ValueError):validate(c,['body','wheel'])

    def test_parent_cycle_and_unbounded_origin_rejected(self):
        for action in ('cycle','missing','nan','outside'):
            c=self.config()
            if action=='cycle':c['groups'][0]['parent']='wheel'
            elif action=='missing':c['groups'][1]['parent']='unknown'
            elif action=='nan':c['groups'][1]['pivot'][0]=float('nan')
            else:c['groups'][1]['pivot'][0]=100
            with self.assertRaises(ValueError):validate(c,['body','wheel'])

    def test_no_code_reduction_or_large_atlas_request(self):
        for change in ({'python':'arbitrary code'},{'triangle_budget':1000},{'generate_lods':True},{'texture_size':8192}):
            c=self.config();c.update(change)
            with self.assertRaises(ValueError):validate(c,['body','wheel'])

    def test_reuse_requires_known_receipt_and_strict_subset(self):
        c=self.config();c['reuse']={'export_id':'a'*32,'groups':['body']};validate(c,['body','wheel'])
        for r in ({'export_id':'../elsewhere','groups':['body']},{'export_id':'a'*32,'groups':[]},{'export_id':'a'*32,'groups':['body','wheel']},{'export_id':'a'*32,'groups':['other']},{'export_id':'a'*32,'groups':['body'],'path':'elsewhere'}):
            bad=copy.deepcopy(c);bad['reuse']=r
            with self.assertRaises(ValueError):validate(bad,['body','wheel'])

    def test_uv_independent_cache_scope_rejects_implicit_or_uv_coordinates(self):
        nodes=[{'type':'ShaderNodeTexImage','name':'image','inputs':[]},{'type':'ShaderNodeNewGeometry','name':'geometry','inputs':[]}]
        s={'nodes':nodes,'links':[['geometry',0,'image',0]]};self.assertTrue(uv_independent_shader(s))
        self.assertFalse(uv_independent_shader({'nodes':nodes,'links':[]}))
        for name in ('ShaderNodeUVMap','ShaderNodeTexCoord','ShaderNodeNormalMap','ShaderNodeTangent','ShaderNodeScript','ShaderNodeGroup'):
            c=copy.deepcopy(s);c['nodes'].append({'type':name,'name':'unsupported','inputs':[]});self.assertFalse(uv_independent_shader(c))
        c=copy.deepcopy(s);c['nodes'].append({'type':'ShaderNodeBsdfPrincipled','name':'pbr','inputs':[['Anisotropic IOR Level',.5]]});self.assertFalse(uv_independent_shader(c))


if __name__=='__main__':unittest.main()
