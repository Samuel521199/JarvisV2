"""Regression tests for meaningful documentation maintenance failures."""
import json
from pathlib import Path
import tempfile
import unittest
from check_docs import validate
from doclib import digest, navigation, write


class DocumentChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-doc-check-')
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.name.startswith('jarvis-doc-check-'))
        for part in ['docs/diagrams','docs/assets','tools']:
            (self.root/part).mkdir(parents=True,exist_ok=True)
        book='<a id="book-tree"></a>\n<!-- book-tree:start -->\n<!-- book-tree:end -->\n'
        write(self.root/'README.md','# Fixture\n\n'+book)
        write(self.root/'docs/README.md','# Index\n\n'+book)
        write(self.root/'docs/topic.md','# Topic\n\n<!-- book-nav:start -->\n<!-- book-nav:end -->\n\n<a id="rule"></a>\n## Rule\n\n[Entry](../README.md)\n\n<!-- book-footer:start -->\n<!-- book-footer:end -->\n')
        self.data={'documents':[
            {'id':'root','path':'README.md','title':'Fixture','owns':['root'],'kind':'entry'},
            {'id':'index','path':'docs/README.md','title':'Index','owns':['index'],'kind':'entry'},
            {'id':'topic','path':'docs/topic.md','title':'Topic','owns':['rule'],'kind':'chapter','reader_summary':'Rules'}],
            'book':{'parts':[{'id':'part','title':'Part','chapters':['topic']}]},'generated_diagrams':[],'assets':[],'required_anchors':{'docs/topic.md':['rule']}}
        self.persist()
        self.sync()

    def tearDown(self):
        self.temp.cleanup()

    def persist(self):
        write(self.root/'docs/manifest.json',json.dumps(self.data))

    def sync(self):
        for path,text in navigation(self.root,self.data).items():
            write(self.root/path,text)

    def test_valid_book_and_idempotent_navigation(self):
        self.assertEqual(validate(self.root)[0],[])
        self.assertTrue(all((self.root/p).read_text(encoding='utf-8')==t for p,t in navigation(self.root,self.data).items()))

    def test_broken_anchor_detected(self):
        p=self.root/'docs/topic.md'
        write(p,p.read_text(encoding='utf-8')+'\n[Missing](#absent)\n')
        self.assertTrue(any('Broken anchor' in e for e in validate(self.root)[0]))

    def test_stale_navigation_detected(self):
        p=self.root/'docs/topic.md'
        write(p,p.read_text(encoding='utf-8').replace('## Rule','## Renamed'))
        self.assertTrue(any('Stale navigation' in e for e in validate(self.root)[0]))

    def test_removed_required_identifier_detected(self):
        p=self.root/'docs/topic.md'
        write(p,p.read_text(encoding='utf-8').replace('id="rule"','id="replacement"'))
        self.sync()
        self.assertTrue(any('Required stable identifier missing' in e for e in validate(self.root)[0]))

    def test_duplicate_ownership_detected(self):
        self.data['documents'][1]['owns']=['root'];self.persist()
        self.assertTrue(any('Duplicate topic ownership' in e for e in validate(self.root)[0]))

    def test_removed_requirement_number_detected(self):
        self.data['required_identifiers']={'docs/topic.md':['R01']};self.persist()
        self.assertTrue(any('Required requirement/validation id missing' in e for e in validate(self.root)[0]))

    def test_changed_figure_detected(self):
        source=self.root/'docs/diagrams/test.mmd';write(source,'flowchart LR\n A-->B\n')
        image=self.root/'docs/diagrams/test.png';image.write_bytes(b'fixture-only')
        self.data['generated_diagrams']=[{'id':'figure','owner_document':'docs/topic.md','source_document':'docs/diagrams/test.mmd','source_sha256':digest(source),'artifacts':[{'path':'docs/diagrams/test.png','sha256':digest(image)}]}]
        p=self.root/'docs/topic.md';write(p,p.read_text(encoding='utf-8')+'\n![Fixture](diagrams/test.png)\n')
        self.persist();image.write_bytes(b'changed-fixture')
        self.assertTrue(any('Missing or changed diagram' in e for e in validate(self.root)[0]))

    def test_absolute_local_reference_rejected(self):
        p=self.root/'docs/topic.md';write(p,p.read_text(encoding='utf-8')+'\n[Bad](Z:/old-project/file.md)\n')
        self.assertTrue(any('Non-portable local link' in e for e in validate(self.root)[0]))


if __name__=='__main__':
    unittest.main()
