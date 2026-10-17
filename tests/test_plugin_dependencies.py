import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from playlite import plugin_manager as manager
from playlite.plugin_dependencies import missing_dependencies,version_key,check_core_version


def archive(identity, version='1.0', deps=None):
    data=io.BytesIO()
    with ZipFile(data,'w') as bundle:
        bundle.writestr('manifest.json',json.dumps(dict(id=identity,name=identity,version=version,api_version=1,type='generic',plugin_dependencies=deps or [])))
        bundle.writestr('plugin.py','from playlite.providers import GenericPlugin\nclass Plugin(GenericPlugin): pass\n')
    return data.getvalue()


class DependencyTests(unittest.TestCase):
    dependency=dict(id='Dependency',repository='owner/dependency',minimum_version='1.1.17')

    def test_core_requirement_is_checked_before_installing_or_loading_code(self):
        from playlite import __version__
        from playlite.providers import discover_plugins
        check_core_version({})
        check_core_version({'minimum_playlite_version': __version__})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / 'plugins/example';plugin.mkdir(parents=True)
            original = dict(id='Example', name='Example', version='1', api_version=1, type='generic')
            (plugin / 'manifest.json').write_text(json.dumps(original))
            (plugin / 'plugin.py').write_text('raise RuntimeError("must not import")')
            incompatible = dict(original, minimum_playlite_version='999.0')
            path = root / 'future.zip'
            with ZipFile(path, 'w') as bundle:
                bundle.writestr('manifest.json', json.dumps(incompatible))
                bundle.writestr('plugin.py', 'raise RuntimeError("must not import")')
            with patch.object(manager.subprocess, 'run') as install:
                with self.assertRaisesRegex(ValueError, 'requires Playlite 999.0'):
                    manager.install_archive(path, root / 'plugins')
                install.assert_not_called()
            self.assertEqual(json.loads((plugin / 'manifest.json').read_text()), original)
            (plugin / 'manifest.json').write_text(json.dumps(incompatible))
            with self.assertLogs(level='ERROR') as log:
                self.assertEqual(set(discover_plugins(root / 'plugins')), {'Manual'})
            self.assertIn('requires Playlite 999.0', '\n'.join(log.output))
            self.assertNotIn('RuntimeError: must not import', '\n'.join(log.output))

    def test_versions_missing_outdated_and_disabled(self):
        manifest=dict(id='Parent',name='Parent',plugin_dependencies=[self.dependency])
        self.assertEqual(version_key('v1.1.17.0'),version_key('1.1.17'))
        self.assertEqual(missing_dependencies(manifest,[]),[self.dependency])
        old=dict(id='Dependency',repository='owner/dependency',version='1.1.9')
        self.assertEqual(missing_dependencies(manifest,[old]),[self.dependency])
        current=dict(old,version='1.1.17')
        self.assertEqual(missing_dependencies(manifest,[current]),[])
        with self.assertRaisesRegex(ValueError,'Enable required'):
            missing_dependencies(manifest,[dict(current,enabled=False)])
        with self.assertRaises(ValueError):
            missing_dependencies(manifest,[dict(current,repository='other/dependency')])

    def test_archive_refuses_missing_dependency_without_changing_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'plugin.zip';path.write_bytes(archive('Parent',deps=[self.dependency]))
            with self.assertRaisesRegex(ValueError,'Required plugins'):
                manager.install_archive(path,root/'plugins')
            self.assertEqual(manager.installed_plugins(root/'plugins'),[])

    def test_github_installs_dependency_before_parent(self):
        dep=archive('Dependency','1.1.17');parent=archive('Parent',deps=[self.dependency])
        def request(path,binary=False):
            if path.endswith('/releases/latest'):
                dependency='/owner/dependency/' in path
                start=3 if dependency else 1
                return {'assets':[dict(name='plugin.zip',id=start),dict(name='SHA256SUMS',id=start+1)]}
            identity=int(path.rsplit('/',1)[1])
            payload=parent if identity in (1,2) else dep
            return payload if identity in (1,3) else (hashlib.sha256(payload).hexdigest()+'  plugin.zip\n').encode()
        with tempfile.TemporaryDirectory() as temporary,patch.object(manager,'github_token',return_value='token'),patch.object(manager,'github_request',side_effect=request):
            result=manager.install_github('owner/parent',directory=Path(temporary))
            self.assertEqual(result['id'],'Parent')
            self.assertEqual({p['id'] for p in manager.installed_plugins(Path(temporary))},{'Dependency','Parent'})

    def test_cycles_and_invalid_declarations_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Circular'):
            manager.install_github('owner/parent',_stack=('owner/parent',))
        with self.assertRaises(ValueError):
            missing_dependencies(dict(id='Dependency',plugin_dependencies=[self.dependency]),[])
