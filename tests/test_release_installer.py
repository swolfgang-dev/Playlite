"""Exercise the real shell installer with offline release and package fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'install.sh'
FAKE_PIP = '''import os,sys,sysconfig
from pathlib import Path
if sys.argv[1]=='check':raise SystemExit(8 if os.environ.get('CHECK_FAIL') else 0)
if os.environ.get('INSTALL_FAIL'):raise SystemExit(7)
site=Path(sysconfig.get_paths()['purelib'])
for package in ('playlite','PyQt6','PIL'):
 (site/package).mkdir(exist_ok=True)
 (site/package/'__init__.py').write_text('')
for name in ('app','cli','plugin_manager'):
 (site/'playlite'/f'{name}.py').write_text("import os,sys\\nfrom pathlib import Path\\nif os.environ.get('VERIFY_FAIL') or (os.environ.get('FINAL_FAIL') and Path(sys.prefix).name=='runtime'):raise ImportError('fixture failure')\\n")
import shutil
for name in ('ownership.py','storage.py'):
 if not os.environ.get('OLDER_RELEASE'):shutil.copy2(Path(os.environ['CORE_SOURCE'])/name,site/'playlite'/name)
(site/'playlite/assets').mkdir()
(site/'playlite/assets/playlite.png').write_bytes(b'icon')
(site/'PyQt6/QtWidgets.py').write_text('')
(site/'PIL/Image.py').write_text('')
for name in ('playlite','playlite-cli','playlite-plugins','playlite-installer'):
 script=Path(sys.prefix)/'bin'/name
 script.write_text('#!'+sys.executable+'\\nprint("fixture executable works")\\n')
 script.chmod(0o755)
'''
PYTHON_SHIM = '''#!/usr/bin/python3
import hashlib,os,sys
from pathlib import Path
if len(sys.argv)>1 and sys.argv[1]=='-':
 code=sys.stdin.read()
 if 'api.github.com/repos/' in code:
  root=Path(sys.argv[4]);wheel=root/'playlite-1.0-py3-none-any.whl'
  wheel.write_bytes(b'fixture wheel')
  pip=root/'pip.pyz';pip.write_bytes(Path(os.environ['FAKE_PIP']).read_bytes())
  for name in ('uninstall.sh','uninstall.py'):
   (root/name).write_bytes((Path(os.environ['CORE_SOURCE']).parent/name).read_bytes())
  (root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\\n' for p in (wheel,pip,root/'uninstall.sh',root/'uninstall.py')))
  raise SystemExit(0)
 sys.argv=sys.argv[1:]
 exec(compile(code,'<installer>','exec'))
else:os.execv('/usr/bin/python3',['/usr/bin/python3',*sys.argv[1:]])
'''


class ReleaseInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        tools = self.root / 'tools'
        tools.mkdir()
        (tools / 'python3').write_text(PYTHON_SHIM)
        (tools / 'python3').chmod(0o755)
        pip = self.root / 'fake-pip.py'
        pip.write_text(FAKE_PIP)
        self.data = self.root / 'data/playlite'
        runtime = self.data / 'runtime'
        (runtime / 'bin').mkdir(parents=True)
        (runtime / 'old-dependency').write_text('obsolete')
        (runtime / 'bin/playlite').write_text('#!/bin/sh\necho old')
        (runtime / 'bin/playlite').chmod(0o755)
        (self.data / 'library.json').write_text('keep user data')
        self.repo_launcher = self.root / 'bin/playlite-dev'
        self.repo_launcher.parent.mkdir()
        self.repo_launcher.write_text('repo launcher')
        self.environment = dict(os.environ, PATH=str(tools)+':'+os.environ['PATH'],
            HOME=str(self.root), XDG_DATA_HOME=str(self.root / 'data'),
            PLAYLITE_BIN_DIR=str(self.root / 'bin'), PLAYLITE_PROFILE='installed', FAKE_PIP=str(pip), CORE_SOURCE=str(INSTALLER.parent/'playlite'))
        for name in ('INSTALL_FAIL','VERIFY_FAIL','FINAL_FAIL','CHECK_FAIL','OLDER_RELEASE'):
            self.environment.pop(name, None)

    def install(self, **flags):
        return subprocess.run(['bash', str(INSTALLER), '--no-gui'], cwd=self.root,
            env=dict(self.environment, **flags), capture_output=True, text=True, timeout=30)

    def assert_preserved(self):
        self.assertEqual((self.data / 'library.json').read_text(), 'keep user data')
        self.assertEqual(self.repo_launcher.read_text(), 'repo launcher')
        self.assertFalse(list(self.data.glob('runtime.new.*')))
        self.assertFalse(list(self.data.glob('runtime.old.*')))

    def test_fresh_update_removes_old_files_and_relocates_launchers(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.data / 'runtime/old-dependency').exists())
        executable = self.root / 'bin/playlite'
        result = subprocess.run([str(executable)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('fixture executable works', result.stdout)
        self.assert_preserved()
        # Reinstalling the same version also uses a clean environment.
        (self.data / 'runtime/stray-file').write_text('untracked')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.data / 'runtime/stray-file').exists())
        self.assert_preserved()

    def test_install_failure_retains_old_runtime(self):
        result = self.install(INSTALL_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.data / 'runtime/old-dependency').exists())
        self.assert_preserved()

    def test_verification_failure_retains_old_runtime(self):
        result = self.install(VERIFY_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.data / 'runtime/old-dependency').exists())
        self.assert_preserved()

    def test_post_switch_failure_rolls_back_runtime(self):
        result = self.install(FINAL_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.data / 'runtime/old-dependency').exists())
        self.assert_preserved()

    def test_dependency_check_failure_retains_old_runtime(self):
        result = self.install(CHECK_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.data / 'runtime/old-dependency').exists())
        self.assert_preserved()

    def test_clean_first_install(self):
        import shutil
        shutil.rmtree(self.data / 'runtime')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.data / 'runtime/bin/playlite').exists())
        self.assert_preserved()

    def test_older_release_still_gets_ownership_receipt(self):
        result = self.install(OLDER_RELEASE='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.data / 'runtime/.playlite-owned.json').exists())
        self.assert_preserved()

    def test_uninstaller_assets_are_recorded_and_manual_scripts_are_preserved(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.data / 'uninstall.sh').exists())
        self.assertTrue((self.data / '.playlite-install-scripts.json').exists())
        (self.data / 'uninstall.sh').write_text('manual replacement')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.data / 'uninstall.sh').read_text(), 'manual replacement')
