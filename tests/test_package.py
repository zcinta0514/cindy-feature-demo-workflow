import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cindy-share-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / '独立 工程'
        self.workflow = module('workflow')

    def test_init_is_independent_and_idempotent(self):
        self.assertEqual(self.workflow.init(self.project)['status'], 'initialized')
        file = self.project / 'production-script.json'
        file.write_text('{"keep":"my work"}')
        self.assertEqual(self.workflow.init(self.project)['status'], 'exists')
        self.assertEqual(json.loads(file.read_text()), {'keep': 'my work'})
        moved = self.base / '移动后的 工程'
        self.project.rename(moved)
        self.assertEqual(self.workflow.doctor(moved)['assetMismatches'], [])
        config = json.loads((moved / 'demo.config.json').read_text())
        self.assertFalse(Path(config['delivery']['root']).is_absolute())

    def test_nonempty_directory_is_preserved(self):
        self.project.mkdir()
        existing = self.project / 'untouched.txt'
        existing.write_text('original')
        with self.assertRaises(ValueError):
            self.workflow.init(self.project)
        self.assertEqual(existing.read_text(), 'original')

    def test_library_restore_rejects_tampering_and_preserves_existing_work(self):
        import gzip
        import hashlib
        lib = module('library')
        fixture = self.base / 'fixture'
        (fixture / 'library/objects').mkdir(parents=True)
        data = b'<!doctype html><title>portable native fixture</title>'
        digest = hashlib.sha256(data).hexdigest()
        (fixture / 'library/catalog.json').write_text(json.dumps({'cases':[{'id':'sample','root':'example'}]}))
        (fixture / 'library/manifest.json').write_text(json.dumps({'files':{'example/index.html':{'sha256':digest,'bytes':len(data)}}}))
        obj = fixture / 'library/objects' / (digest + '.gz')
        obj.write_bytes(gzip.compress(b'corrupted'))
        lib.ROOT = fixture
        self.workflow.init(self.project)
        with self.assertRaises(ValueError):lib.restore(self.project, 'sample')
        self.assertFalse((self.project/'production-library').exists())
        obj.write_bytes(gzip.compress(data))
        self.assertEqual(lib.restore(self.project, 'sample')['status'], 'restored')
        self.assertEqual((self.project/'production-library/example/index.html').read_bytes(), data)
        with self.assertRaises(ValueError):lib.restore(self.project, 'sample')
        with self.assertRaises(ValueError):lib.safe(self.project,'../outside')

    def test_library_catalog_and_source_parts_are_complete(self):
        import hashlib
        manifest=json.loads((ROOT/'library/manifest.json').read_text())
        catalog=json.loads((ROOT/'library/catalog.json').read_text())
        for case in catalog['cases']:
            self.assertIn(case['entry'],manifest['files'])
        for name,info in manifest['files'].items():
            self.assertNotIn('..',Path(name).parts)
            if (ROOT/'library/objects').exists():self.assertTrue((ROOT/'library/objects'/(info['sha256']+'.gz')).is_file())
        h=hashlib.sha256()
        if (ROOT/manifest['sourceArchive']['parts'][0]).exists():
            for part in manifest['sourceArchive']['parts']:h.update((ROOT/part).read_bytes())
            self.assertEqual(h.hexdigest(),manifest['sourceArchive']['sha256'])
        else:
            payload=json.loads((ROOT/'library/payload.json').read_text())
            self.assertRegex(payload['sha256'],r'^[0-9a-f]{64}$')

    def test_offline_resource_bundle_is_verified_before_restore(self):
        import gzip, hashlib, zipfile
        lib=module('library');fixture=self.base/'small-skill';(fixture/'library').mkdir(parents=True)
        data=b'<!doctype html><title>offline</title>';h=hashlib.sha256(data).hexdigest();packed=gzip.compress(data)
        (fixture/'library/catalog.json').write_text(json.dumps({'cases':[{'id':'offline','root':'example'}]}))
        (fixture/'library/manifest.json').write_text(json.dumps({'files':{'example/index.html':{'sha256':h,'bytes':len(data)}}}))
        resource=self.base/'resources.zip'
        with zipfile.ZipFile(resource,'w') as z:z.writestr('library/objects/'+h+'.gz',packed)
        payload={'sha256':hashlib.sha256(resource.read_bytes()).hexdigest(),'bytes':resource.stat().st_size,'uncompressedBytes':len(packed)}
        (fixture/'library/payload.json').write_text(json.dumps(payload));lib.ROOT=fixture
        self.workflow.init(self.project)
        result=lib.restore(self.project,'offline',resources=resource)
        self.assertEqual(result['status'],'restored')
        self.assertEqual((self.project/'production-library/example/index.html').read_bytes(),data)
        self.assertTrue((self.project/'.workflow-resources/payload-sha256.txt').is_file())

    def test_relative_delivery_root_and_missing_qa_are_held(self):
        self.workflow.init(self.project)
        manifest = self.project / 'output/test.json'
        manifest.write_text(json.dumps({'schemaVersion': 1, 'id': 'calibration', 'version': 'v1', 'delivery': {}}))
        archive = module('archive_delivery')
        result = archive.archive(manifest, self.project / 'demo.config.json')
        self.assertEqual(result['category'], 'held')
        self.assertTrue(Path(result['path']).is_relative_to((self.project / 'deliveries').resolve()))
        self.assertFalse((self.project / 'deliveries/发送记录.csv').exists())

    def test_references_and_json_are_self_contained(self):
        for file in ROOT.rglob('*.json'):
            if 'node_modules' not in file.parts:
                json.loads(file.read_text())
        for file in ROOT.rglob('*.md'):
            if 'node_modules' in file.parts:
                continue
            for link in re.findall(r'\]\(([^)]+)\)', file.read_text()):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((file.parent / link.split('#')[0]).exists(), (file, link))

    def test_complete_target_fit_and_inverse_cursor(self):
        code = '''
import {fitTargets,point,inverse} from './assets/runtime/camera.mjs';
import assert from 'node:assert/strict';
for(const target of [{x:100,y:200,width:1200,height:900},{x:30,y:20,width:3000,height:2000},{x:800,y:700,width:450,height:200}]){
 const viewport={x:0,y:100,width:1440,height:880};
 const pose=fitTargets([target],viewport);
 const a=point(target,pose),b=point({x:target.x+target.width,y:target.y+target.height},pose);
 assert(a.x>=31.99&&a.y>=131.99&&b.x<=1408.01&&b.y<=948.01);
 const restored=inverse(point({x:410,y:320},pose),pose);assert(Math.abs(restored.x-410)<1e-9&&Math.abs(restored.y-320)<1e-9);
}
'''
        subprocess.run(['node', '--input-type=module', '-e', code], cwd=ROOT, check=True)

    def test_distributable_excludes_generated_and_local_files(self):
        files = module('package').members()
        self.assertTrue(files)
        for file in files:
            self.assertNotIn('node_modules', file.parts)
            self.assertNotIn(file.suffix, ('.mp4', '.zip', '.pyc'))
            self.assertFalse(file.is_symlink())
            if file.suffix in ('.md', '.json', '.js', '.mjs', '.py', '.css'):
                text = file.read_text()
                self.assertIsNone(re.search(r'/(?:Users|home)/[A-Za-z0-9_-]+/', text), file)
                self.assertNotIn('remote-' + 'agent/workspaces/', text, file)


if __name__ == '__main__':
    unittest.main(verbosity=2)
