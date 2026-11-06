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
