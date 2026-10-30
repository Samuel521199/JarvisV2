import math
import unittest
from modules.skills.studio3d.trail_details import add_trail_fittings
from modules.skills.studio3d.assembly_geometry import sub,norm


class TrailDetailTests(unittest.TestCase):
    def collect(self,label):
        s=1 if label=='left' else -1;a=[-.2,s*.35,.49];end=[-2.85,s*1.58,.20];objects=[];bolts=[]
        def mesh(name,data,group,**kwargs):objects.append((name,data,group,kwargs))
        def bolt(pos,axis,group,r):bolts.append((pos,axis,group,r))
        receipt=add_trail_fittings(a,end,.078,label,mesh,bolt)
        return a,end,objects,bolts,receipt

    def test_per_side_batched_and_on_real_sleeves(self):
        for label in ('left','right'):
            a,end,objects,bolts,receipt=self.collect(label);self.assertEqual(len(objects),1);self.assertEqual(len(bolts),12)
            self.assertEqual(objects[0][0],'trail-strap-details-'+label);self.assertEqual(objects[0][2],'trail-'+label)
            self.assertEqual(receipt['collar_fractions'],[.27,.64,.90]);self.assertTrue(receipt['visual_only'])
            direction=sub(end,a);axis=norm(direction);length=math.sqrt(sum(x*x for x in direction))
            for i,(pos,normal,group,radius) in enumerate(bolts):
                delta=sub(pos,a);t=sum(delta[j]*axis[j] for j in range(3))/length
                self.assertAlmostEqual(t,[.27,.64,.90][i//4],delta=.012)
                self.assertEqual(group,'trail-'+label);self.assertAlmostEqual(sum(x*x for x in normal),1,places=6)
                self.assertGreater(radius,0)
            self.assertLess(len(objects[0][1].vertices),1500)

    def test_rejects_invalid_ranges_and_degenerate_axes(self):
        noop=lambda *args,**kw:None
        for a,end,r,label in (([0,0,0],[0,0,0],.078,'left'),([0,0,0],[-3,0,0],.2,'left'),([0,0,0],[-3,0,0],.078,'other'),([0,0,0],[-3,0,float('nan')],.078,'left')):
            with self.assertRaises(ValueError):add_trail_fittings(a,end,r,label,noop,noop)

    def test_attached_fittings_fit_scene_contract(self):
        from modules.skills.studio3d.artillery_recipe import build,parameters
        from modules.skills.studio3d.assembly_geometry import Mesh,add,mul
        from modules.skills.studio3d.contract import validate
        p=parameters({'trail_spread':1.58,'spade_detail':3,'wheel_form':4,'control_detail':2,'rear_detail':2,'shield_hardware':1,'finish_detail':2})
        scene,_=build(p);objects=scene['objects']
        def mesh(name,data,group,**kwargs):objects.append(data.object(name,'paint',**kwargs))
        def bolt(pos,axis,group,r):
            obj=next(o for o in objects if o['id']=='fasteners-'+group);part=Mesh()
            part.tube(add(pos,mul(axis,-.003)),add(pos,mul(axis,.012)),r,segments=6,rounded=False)
            verts=obj['params']['vertices'];faces=obj['params']['faces'];offset=len(verts)
            verts.extend(part.vertices);faces.extend([[offset+i for i in face] for face in part.faces])
        for sign,label in ((1,'left'),(-1,'right')):
            add_trail_fittings([-.2,sign*.35,.49],[-p['trail_length'],sign*p['trail_spread'],.2],p['trail_radius'],label,mesh,bolt)
        result=validate(scene)
        self.assertEqual(sum(o['id'].startswith('trail-strap-details-') for o in result['objects']),2)

if __name__=='__main__':unittest.main()
