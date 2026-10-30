# SPDX-License-Identifier: GPL-2.0-or-later
"""Small, reversible eyelid/iris proportion trial for one known character."""


def apply():
    import bpy
    records=[]
    for side in ('r','l'):
        for kind in ('iris','pupil'):
            name='eye-'+kind+'-'+side
            obj=bpy.data.objects.get(name)
            if not obj or obj.type!='MESH':raise ValueError('Expected eye accent missing: '+name)
            prior=list(obj.scale)
            obj.scale.z*=.86
            records.append({'name':name,'previous_scale':prior,'z_scale_multiplier':.86})
        name='eye-upper-lid-'+side
        lid=bpy.data.objects.get(name)
        if not lid or lid.type!='CURVE':raise ValueError('Expected eyelid missing: '+name)
        prior=list(lid.location);lid.location.z-=.001
        records.append({'name':name,'previous_location':prior,'z_offset_m':-.001})
    return {'scope':'existing procedural eye accents only; no body, facial mesh or hair changes',
            'changes':records,'limits':['eye-white geometry, face shape, nose and mouth unchanged',
                                         'material appearance and reference similarity require visual review'],
            'status':'candidate; no user approval'}
