import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/python"))

from flypy_codec import (
    convert_to_flypy,
    is_valid_flypy_code,
    is_valid_quanpin_code,
    is_valid_word_code_pair,
    keyword_char_length,
    normalize_pinyin_text,
)


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

    def test_quanpin_code_validation(self):
        self.assertTrue(is_valid_quanpin_code("zhong guo"))
        self.assertTrue(is_valid_quanpin_code("a"))
        self.assertFalse(is_valid_quanpin_code("háng zhǎng"))
        self.assertFalse(is_valid_quanpin_code(""))
        self.assertFalse(is_valid_quanpin_code("zhong guo1"))

    def test_keyword_char_length_strips_separators(self):
        self.assertEqual(keyword_char_length("中国"), 2)
        self.assertEqual(keyword_char_length("玛丽亚·凯莉"), 5)
        self.assertEqual(keyword_char_length("A—B–C ·"), 3)

    def test_word_code_pair_matches_awk_rule(self):
        self.assertTrue(is_valid_word_code_pair("中国", "vs go"))
        self.assertTrue(is_valid_word_code_pair("行长", "hh vh"))
        self.assertTrue(is_valid_word_code_pair("玛丽亚·凯莉", "ma li ya kai li"))
        # 字数与音节数不一致，对应 AWK 校验命中的不合法词条
        self.assertFalse(is_valid_word_code_pair("行长行长", "hh vh"))
        # 词中含未剥离字符（如字母）时按字数计入
        self.assertFalse(is_valid_word_code_pair("5G网络", "wang luo"))
        self.assertFalse(is_valid_word_code_pair("中国", ""))


if __name__ == "__main__":
    unittest.main()
