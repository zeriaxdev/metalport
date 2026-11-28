"""The release guard rejects game, engine and Unity data files and accepts our own sources."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_no_game_files import problems


class NoGameFiles(unittest.TestCase):
    def test_rejects_game_engine_and_unity_data(self):
        bad = [('x/UnityPlayer.dylib', 1), ('Game_Data/sharedassets0.assets', 1), ('a/b/globalgamemanagers', 1),
               ('level0', 1), ('ports/Game.app/Contents/Info.plist', 1), ('work/unity/x.txt', 1),
               ('Game/steam_api64.dll', 1), ('big.py', 3 * 1024 * 1024)]
        self.assertEqual(len(problems(bad)), len(bad))

    def test_accepts_our_sources(self):
        good = [('tools/port.py', 4000), ('docs/PIPELINE.md', 9000), ('games/repo.json', 700),
                ('tests/test_dxbc_rdef.py', 5000), ('tools/levelmap.py', 100)]
        self.assertEqual(problems(good), [])


if __name__ == '__main__':
    unittest.main()
