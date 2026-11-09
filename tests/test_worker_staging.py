"""Staging visits only the allowed stdlib tree; no site-package traversal."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from control.worker.runtime import stdlib_sources


class WorkerStaging(unittest.TestCase):
    def test_excluded_subtrees_are_never_enumerated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('pkg','site-packages/deep','tests/deep','__pycache__/deep'):(root/name).mkdir(parents=True)
            for name in ('a.py','pkg/b.py','site-packages/deep/hook.py','tests/deep/test.py'):(root/name).write_text('pass',encoding='utf-8')
            scanned=[];real=os.scandir
            def scan(path):
                relative=Path(path).relative_to(root)
                self.assertFalse({'site-packages','tests','__pycache__'} & set(relative.parts))
                scanned.append(relative);return real(path)
            with patch('control.worker.runtime.os.scandir',side_effect=scan):sources=stdlib_sources(root)
            self.assertEqual([p.relative_to(root).as_posix() for p in sources],['a.py','pkg/b.py'])
            self.assertEqual(set(scanned),{Path('.'),Path('pkg')})
