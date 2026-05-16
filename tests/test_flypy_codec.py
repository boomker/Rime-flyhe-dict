import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/python"))

from flypy_codec import convert_to_flypy, is_valid_flypy_code, normalize_pinyin_text


class FlypyCodecTest(unittest.TestCase):
    def test_normalize_tone_marks(self):
        self.assertEqual(normalize_pinyin_text("háng zhǎng"), "hang zhang")

    def test_normalize_umlaut_and_tone_numbers(self):
        self.assertEqual(normalize_pinyin_text("lǜe nv3"), "lve nv")

    def test_convert_toned_pinyin_matches_plain_pinyin(self):
        self.assertEqual(
            convert_to_flypy("háng zhǎng"), convert_to_flypy("hang zhang")
        )

    def test_existing_flypy_code_is_stable(self):
        self.assertEqual(convert_to_flypy("vs go"), "vs go")

    def test_invalid_hybrid_code_can_be_detected(self):
        self.assertFalse(is_valid_flypy_code("háng vǎng"))
        self.assertTrue(is_valid_flypy_code("hh vh"))


if __name__ == "__main__":
    unittest.main()
