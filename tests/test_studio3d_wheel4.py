import math
import unittest
from collections import defaultdict, deque

from modules.skills.studio3d.artillery_recipe import build, pressed_wheel_plate
from modules.skills.studio3d.semantic_patch import merge


class ContinuousPressedWheelTests(unittest.TestCase):
    def test_plate_faces_are_one_connected_closed_surface(self):
        plate, depth = pressed_wheel_plate(.975, .145, .45, 8)
        adjacency = defaultdict(set)
        edge_counts = defaultdict(int)
        for face in plate.faces:
            for a, b in zip(face, face[1:] + face[:1]):
                adjacency[a].add(b); adjacency[b].add(a)
                edge_counts[tuple(sorted((a, b)))] += 1
        visited = set(); queue = deque([0])
        while queue:
            vertex = queue.popleft()
            if vertex in visited: continue
            visited.add(vertex); queue.extend(adjacency[vertex] - visited)
        self.assertEqual(len(visited), len(plate.vertices))
        self.assertTrue(all(count == 2 for count in edge_counts.values()))
        self.assertGreater(depth(.25, 0), depth(.25, math.pi / 8))
        self.assertLess(depth(.25, 0) - depth(.25, math.pi / 8), .02)

    def test_variant_keeps_every_other_semantic_group_unchanged(self):
        before, bsem = build({'wheel_form': 3})
        after, asem = build({'wheel_form': 4})
        groups = {'wheel-left', 'wheel-right'}
        original = {o['id']: o for o in before['objects'] if bsem['groups'][o['id']] not in groups}
        changed = {o['id']: o for o in after['objects'] if asem['groups'][o['id']] not in groups}
        self.assertEqual(original, changed)
        self.assertNotIn('ribs-left', {o['id'] for o in after['objects']})
        self.assertEqual(asem['motion_owners']['disc-left'], 'wheel-left')
        result, sem = merge(before, bsem, after, asem, [{'parameter': 'wheel_form', 'group': 'wheels'}])
        self.assertEqual(sem['mutation_receipt']['declared_groups'], sorted(groups))
        self.assertEqual(len(result['objects']), len(after['objects']))

    def test_both_face_fasteners_start_inside_sheet(self):
        y, w, rad, count = .975, .145, .45, 8
        scene, _ = build({'wheel_form': 4})
        fasteners = next(o for o in scene['objects'] if o['id'] == 'fasteners-wheel-left')
        verts = fasteners['params']['vertices']
        _, depth = pressed_wheel_plate(y, w, rad, count)
        # First 16 hexagonal bolts are seated into the sheet on both sides.
        for side_index, side in enumerate((-1, 1)):
            for i in range(count):
                t = (i + .5) * math.tau / count; r = rad * .39
                bolt_vertices = verts[(side_index * count + i) * 14:(side_index * count + i + 1) * 14]
                axial = [side * (v[1] - y) for v in bolt_vertices]
                self.assertLessEqual(min(axial), depth(r, t))
                self.assertGreater(max(axial), depth(r, t))


if __name__ == '__main__': unittest.main()

