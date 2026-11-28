"""Synthetic Steam app cache; the real Steam folder is never touched.

Adapted from the tests of zeriaxdev/buckshot-roulette-mac (same owner, MIT) for the generalised steam_entry.py.
"""
import hashlib
import plistlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import steam_entry as se

APP_ID, NAME = 424242, 'Test Game'


def record(appid, tree, strings):
    payload = se.encode(tree, strings)
    return struct.pack('<II', appid, 60 + len(payload)) + bytes(40) + hashlib.sha1(payload).digest() + payload


def fake_cache(path, osextended=True):
    """Another game, then ours shaped like Steam's record (Windows-only, one public depot, one save root)."""
    strings = []
    other = record(10, {'appinfo': (0, {'common': (0, {'name': (1, 'Other Game')})})}, strings)
    common = {'name': (1, NAME), 'oslist': (1, 'windows')}
    if osextended:
        common['osextended'] = (1, '')
    ours = record(APP_ID, {'appinfo': (0, {
        'common': (0, common),
        'config': (0, {'launch': (0, {'0': (0, {'executable': (1, 'Game.exe')})})}),
        'depots': (0, {'424243': (0, {'manifests': (0, {'public': (0, {'gid': (1, '999')})})}),
                       'branches': (0, {'public': (0, {'buildid': (2, struct.pack('<I', 1234))})})}),
        'ufs': (0, {'savefiles': (0, {'0': (0, {'root': (1, 'WinAppDataLocalLow'), 'path': (1, 'Company/Product/*.sav')})})}),
    })}, strings)
    body = other + ours + struct.pack('<I', 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack('<IIQ', se.MAGIC, 1, 16 + len(body)) + body
                     + struct.pack('<I', len(strings)) + b''.join(s.encode() + b'\0' for s in strings))


class SteamEntryChecks(unittest.TestCase):
    def setUp(self):
        se.configure(APP_ID, NAME, exe='TestExe')
        se.CLOUD = False
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.steam = root / 'Steam'
        self.p = se.paths(self.steam)
        fake_cache(self.p['cache'])
        (self.steam / 'steamapps/common').mkdir(parents=True)
        self.app = root / 'Applications' / (NAME + '.app')
        (self.app / 'Contents/MacOS').mkdir(parents=True)
        (self.app / 'Contents/MacOS/TestExe').write_bytes(b'binary')
        (self.app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'test.game.port'}))
        self.patches = [patch('steam_entry.steam_running', return_value=False),
                        patch('steam_entry.app_archs', return_value={'arm64'})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        se.CLOUD = False
        self.tmp.cleanup()

    def records(self):
        return dict(se.read_cache(self.p['cache'])[2])

    def tree(self):
        return se.load(self.p['cache'])[-1]['appinfo'][1]

    def test_add_sets_up_play_and_touches_no_other_game(self):
        before = self.records()
        se.add(self.app, self.steam)
        self.assertEqual(before[10], self.records()[10])
        tree = self.tree()
        self.assertEqual(tree['common'][1]['oslist'][1], 'windows,macos')
        self.assertEqual(tree['common'][1]['osextended'][1], 'macos64,macosapplesilicon')
        launch = tree['config'][1]['launch'][1]
        self.assertTrue(any(se.ours(e) for e in launch.values()))
        self.assertEqual(launch['0'][1]['config'][1]['oslist'][1], 'windows')   # the .exe entry no longer shows on Mac
        self.assertIn('"buildid"\t\t"1234"', self.p['manifest'].read_text())
        self.assertIn('"424243"', self.p['manifest'].read_text())               # unrestricted depot recorded as installed
        self.assertEqual((self.p['folder'] / se.LAUNCH_EXE).resolve(), self.app.resolve())
        self.assertTrue(se.status(self.steam).startswith('on'))

    def test_add_twice_changes_nothing_more(self):
        se.add(self.app, self.steam)
        first = self.p['cache'].read_bytes()
        se.add(self.app, self.steam)
        self.assertEqual(first, self.p['cache'].read_bytes())

    def test_remove_restores_the_original_record(self):
        for osextended in (True, False):
            with self.subTest(osextended=osextended):
                fake_cache(self.p['cache'], osextended)
                original = self.records()
                se.add(self.app, self.steam)
                se.remove(self.steam)
                # Added key names stay in Steam's shared string table; every record's data is identical again.
                self.assertEqual(original, self.records())
                self.assertFalse(self.p['manifest'].exists() or self.p['folder'].exists() or self.p['receipt'].exists())
                self.assertEqual(se.status(self.steam), 'off')

    def test_cloud_override_is_added_and_removed(self):
        se.CLOUD = True
        original = self.records()
        se.add(self.app, self.steam)
        overrides = self.tree()['ufs'][1]['rootoverrides'][1]
        self.assertEqual(len(overrides), 1)
        self.assertEqual(next(iter(overrides.values()))[1]['root'][1], 'WinAppDataLocalLow')
        se.remove(self.steam)
        self.assertEqual(original, self.records())

    def test_refuses_while_steam_runs(self):
        original = self.p['cache'].read_bytes()
        with patch('steam_entry.steam_running', return_value=True):
            with self.assertRaisesRegex(se.SteamEntryError, 'Quit Steam'):
                se.add(self.app, self.steam)
            with self.assertRaisesRegex(se.SteamEntryError, 'Quit Steam'):
                se.remove(self.steam)
        self.assertEqual(original, self.p['cache'].read_bytes())
        self.assertFalse(self.p['manifest'].exists())

    def test_refuses_unknown_or_damaged_caches_unchanged(self):
        good = self.p['cache'].read_bytes()
        for bad in (struct.pack('<I', 0x07564428) + good[4:], good[:-30], good[:200]):
            with self.subTest(size=len(bad)):
                self.p['cache'].write_bytes(bad)
                with self.assertRaises(se.SteamEntryError):
                    se.add(self.app, self.steam)
                self.assertEqual(bad, self.p['cache'].read_bytes())

    def test_leaves_another_install_alone(self):
        self.p['manifest'].parent.mkdir(parents=True, exist_ok=True)
        self.p['manifest'].write_text('"AppState"\n{\n\t"installdir"\t\t"Some Other Folder"\n}\n')
        with self.assertRaisesRegex(se.SteamEntryError, 'another'):
            se.add(self.app, self.steam)
        self.assertIn('Some Other Folder', self.p['manifest'].read_text())


if __name__ == '__main__':
    unittest.main()
