"""Regression: a fully white capture must not pass merely because every pixel is lit."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from PIL import Image

spec = importlib.util.spec_from_file_location('gameplay_compare', Path(__file__).parent / 'gameplay/compare.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class GameplayCaptureChecks(unittest.TestCase):
    def test_solid_white_and_black_are_not_scene_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, color in [('white', (255, 255, 255)), ('black', (0, 0, 0))]:
                path = Path(folder) / (name + '.png')
                Image.new('RGB', (32, 32), color).save(path)
                result = comparison.capture_stats(path)
                self.assertFalse(result['looks_rendered'], name)
                self.assertEqual(result['colors'], 1)

    def test_detailed_frame_and_one_pixel_difference(self):
        with tempfile.TemporaryDirectory() as folder:
            left, right = Path(folder) / 'a.png', Path(folder) / 'b.png'
            image = Image.new('RGB', (32, 32))
            image.putdata([(x * 8, y * 8, (x + y) * 4) for y in range(32) for x in range(32)])
            image.save(left)
            self.assertTrue(comparison.capture_stats(left)['looks_rendered'])
            image.putpixel((0, 0), (255, 0, 0))
            image.save(right)
            result = comparison.compare_images(left, right)
            self.assertEqual(result['different_pixels'], 1)
            self.assertEqual(result['max_rgb_error_0_255'], 255)
