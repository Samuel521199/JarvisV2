import json,os,sqlite3,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from tools.migrate_codex_home import copy_home,redirect_home,independent_disks
from sdk.protocol import CoreError


class CodexHomeMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
        self.source=self.base/'old';(self.source/'sessions').mkdir(parents=True)
        (self.source/'sessions/rollout-test.jsonl').write_text('{"message":"preserve memory"}\n')
        (self.source/'config.toml').write_text('model = "unchanged"\n')
        (self.source/'auth.json').write_text('{"synthetic_token":"opaque fixture"}')
        db=sqlite3.connect(self.source/'memories_1.sqlite')
        try:db.execute('CREATE TABLE memories(value)');db.execute("INSERT INTO memories VALUES('current correction')");db.commit()
        finally:db.close()

    def test_active_client_refuses_without_creating_new_home(self):
        with patch('tools.migrate_codex_home.active_clients',return_value=[{'Id':123}]):
            with self.assertRaisesRegex(RuntimeError,'Close all Codex'):copy_home(self.source,self.base/'new',self.base/'backup.zip')
        self.assertFalse((self.base/'new').exists());self.assertTrue(self.source.exists())

    def test_recovery_volume_space_is_checked_before_any_original_retirement(self):
        archive=self.base/'archives/backup.zip'
        def space(path):
            from collections import namedtuple
            return namedtuple('Space','total used free')(3*1024**3,0,0 if Path(path)==archive.parent else 3*1024**3)
        with patch('tools.migrate_codex_home.active_clients',return_value=[]),patch('tools.migrate_codex_home.shutil.disk_usage',side_effect=space):
            with self.assertRaisesRegex(ValueError,'recovery volume'):copy_home(self.source,self.base/'new',archive)
        self.assertTrue((self.source/'auth.json').exists());self.assertFalse(archive.exists())

    def test_same_physical_disk_is_refused_even_for_different_drive_letters(self):
        from subprocess import CompletedProcess
        with patch('tools.migrate_codex_home.subprocess.run',return_value=CompletedProcess([],0,'{"primary_disk":1,"backup_disk":1}')):
            with self.assertRaisesRegex(ValueError,'different physical'):independent_disks()
        with patch('tools.migrate_codex_home.subprocess.run',return_value=CompletedProcess([],0,'{"primary_disk":1,"backup_disk":0}')):
            self.assertEqual(independent_disks(),{'primary_disk':1,'backup_disk':0})

    @unittest.skipUnless(os.name=='nt','Actual NTFS junction requires Windows')
    def test_archive_parent_junction_cannot_silently_redirect_the_backup(self):
        import subprocess
        elsewhere=self.base/'elsewhere';elsewhere.mkdir();link=self.base/'redirected-archive'
        command="New-Item -ItemType Junction -Path '"+str(link)+"' -Target '"+str(elsewhere)+"' | Out-Null"
        subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,check=True)
        try:
            with patch('tools.migrate_codex_home.active_clients',return_value=[]):
                with self.assertRaises(CoreError) as error:copy_home(self.source,self.base/'new',link/'backup.zip')
            self.assertEqual(error.exception.code,'unsafe_path')
            self.assertFalse((self.base/'new').exists());self.assertTrue((self.source/'auth.json').exists())
            self.assertFalse((elsewhere/'backup.zip').exists())
        finally:link.rmdir()

    def test_offline_copy_preserves_memory_auth_bytes_and_recovery_archive(self):
        with patch('tools.migrate_codex_home.active_clients',return_value=[]):
            result=copy_home(self.source,self.base/'new',self.base/'backup.zip')
        self.assertEqual((self.base/'new/sessions/rollout-test.jsonl').read_bytes(),(self.source/'sessions/rollout-test.jsonl').read_bytes())
        self.assertEqual((self.base/'new/auth.json').read_bytes(),(self.source/'auth.json').read_bytes())
        self.assertFalse(result['original_removed']);self.assertIn('memories_1.sqlite',result['sqlite_integrity_ok'])
        with zipfile.ZipFile(self.base/'backup.zip') as archive:self.assertIsNone(archive.testzip())

    def test_reappearing_client_never_removes_original_or_claims_cutover(self):
        with patch('tools.migrate_codex_home.active_clients',side_effect=[[],[{'Id':456}]]):
            with self.assertRaisesRegex(RuntimeError,'Close all Codex'):copy_home(self.source,self.base/'new',self.base/'backup.zip')
        self.assertTrue((self.source/'sessions/rollout-test.jsonl').exists())

    def test_archive_content_change_refuses_even_with_valid_zip_crc(self):
        original_write=zipfile.ZipFile.write
        def changed_write(archive,filename,*args,**kwargs):
            item=Path(filename)
            if item.name!='auth.json':return original_write(archive,filename,*args,**kwargs)
            saved=item.read_bytes()
            try:
                item.write_bytes(b'{"synthetic_token":"changed during archive"}')
                return original_write(archive,filename,*args,**kwargs)
            finally:item.write_bytes(saved)
        with patch('tools.migrate_codex_home.active_clients',return_value=[]),patch.object(zipfile.ZipFile,'write',changed_write):
            with self.assertRaisesRegex(ValueError,'ZIP does not match'):copy_home(self.source,self.base/'new',self.base/'backup.zip')
        self.assertIn('opaque fixture',(self.source/'auth.json').read_text())

    @unittest.skipUnless(os.name=='nt','Actual NTFS junction requires Windows')
    def test_real_junction_cutover_preserves_original_until_cleanup(self):
        source=self.base/'.codex';self.source.rename(source);target=self.base/'new';env=[]
        with patch('tools.migrate_codex_home.active_clients',return_value=[]),patch.object(Path,'home',return_value=self.base):
            copy_home(source,target,self.base/'backup.zip')
            retired=redirect_home(source,target,set_home=env.append)
        try:
            self.assertTrue(source.is_junction());self.assertEqual(source.resolve(),target.resolve())
            self.assertEqual(env,[str(target)])
            self.assertEqual((retired/'auth.json').read_bytes(),(source/'auth.json').read_bytes())
        finally:
            if source.is_junction():source.rmdir()

    @unittest.skipUnless(os.name=='nt','Actual NTFS junction requires Windows')
    def test_environment_failure_removes_only_junction_and_restores_original(self):
        source=self.base/'.codex';self.source.rename(source);target=self.base/'new'
        def refuse_environment(_):raise OSError('fixture registry failure')
        with patch('tools.migrate_codex_home.active_clients',return_value=[]),patch.object(Path,'home',return_value=self.base):
            copy_home(source,target,self.base/'backup.zip')
            with self.assertRaisesRegex(OSError,'fixture registry failure'):redirect_home(source,target,set_home=refuse_environment)
        self.assertFalse(source.is_junction());self.assertTrue((source/'auth.json').is_file())
        self.assertEqual((source/'auth.json').read_bytes(),(target/'auth.json').read_bytes())
        self.assertEqual(list(self.base.glob('.codex-before-E-*')),[])
