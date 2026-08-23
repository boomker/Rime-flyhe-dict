import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/python"))

from crawl_net_hot_dict import (  # noqa: E402
    ENCODING_FLYPY,
    ENCODING_QUANPIN,
    dict_file_paths,
    merge_dict_files,
    process_diff_sg_file,
    sghot_header_template,
)


class CrawlNetHotDictEncodingTest(unittest.TestCase):
    def test_dict_file_paths_per_encoding(self):
        self.assertEqual(
            dict_file_paths(ENCODING_FLYPY),
            ("flypy_sghot.dict.yaml", "flypy_dyhot.dict.yaml"),
        )
        self.assertEqual(
            dict_file_paths(ENCODING_QUANPIN),
            ("flypy_sghot_quanpin.dict.yaml", "flypy_dyhot_quanpin.dict.yaml"),
        )

    def test_sghot_header_keeps_dict_name_in_both_encodings(self):
        for encoding in (ENCODING_FLYPY, ENCODING_QUANPIN):
            header = sghot_header_template(encoding).format(timestamp="2026-08-23")
            self.assertIn("name: flypy_sghot", header)
            self.assertIn("version: 2026-08-23", header)
        self.assertIn("全拼", sghot_header_template(ENCODING_QUANPIN))
        self.assertNotIn("全拼", sghot_header_template(ENCODING_FLYPY))


class CrawlNetHotDictBuildTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _write_diff(self, lines):
        diff_file = Path(self._tmp.name) / "diff_sg.txt"
        diff_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(diff_file)

    def test_flypy_mode_converts_quanpin_to_flypy(self):
        sghot_file = str(Path(self._tmp.name) / "flypy_sghot.dict.yaml")
        added = process_diff_sg_file(
            self._write_diff(["中国\tzhong guo\t100"]),
            sghot_file,
            "2026-08-23",
            ENCODING_FLYPY,
        )
        self.assertEqual(added, 1)
        content = Path(sghot_file).read_text(encoding="utf-8")
        self.assertIn("中国\tvs go\t100", content)

    def test_quanpin_mode_keeps_toneless_quanpin(self):
        sghot_file = str(Path(self._tmp.name) / "flypy_sghot_quanpin.dict.yaml")
        added = process_diff_sg_file(
            self._write_diff(["中国\tzhong guo\t100", "行长\tháng zhǎng\t100"]),
            sghot_file,
            "2026-08-23",
            ENCODING_QUANPIN,
        )
        self.assertEqual(added, 2)
        content = Path(sghot_file).read_text(encoding="utf-8")
        self.assertIn("中国\tzhong guo\t100", content)
        self.assertIn("行长\thang zhang\t100", content)
        self.assertNotIn("háng", content)

    def test_invalid_code_lines_are_skipped(self):
        sghot_file = str(Path(self._tmp.name) / "flypy_sghot_quanpin.dict.yaml")
        added = process_diff_sg_file(
            self._write_diff(["坏词\t123\t100", "好词\thao ci\t100"]),
            sghot_file,
            "2026-08-23",
            ENCODING_QUANPIN,
        )
        self.assertEqual(added, 1)
        content = Path(sghot_file).read_text(encoding="utf-8")
        self.assertIn("好词\thao ci\t100", content)
        self.assertNotIn("坏词", content)

    def test_existing_keywords_are_not_duplicated(self):
        sghot_file = str(Path(self._tmp.name) / "flypy_sghot_quanpin.dict.yaml")
        diff_file = self._write_diff(["中国\tzhong guo\t100"])
        self.assertEqual(
            process_diff_sg_file(diff_file, sghot_file, "2026-08-23", ENCODING_QUANPIN),
            1,
        )
        self.assertEqual(
            process_diff_sg_file(diff_file, sghot_file, "2026-08-23", ENCODING_QUANPIN),
            0,
        )
        content = Path(sghot_file).read_text(encoding="utf-8")
        self.assertEqual(content.count("中国\tzhong guo\t100"), 1)

    def test_merge_dyhot_into_quanpin_sghot(self):
        tmp = Path(self._tmp.name)
        dyhot_file = tmp / "flypy_dyhot_quanpin.dict.yaml"
        sghot_file = tmp / "flypy_sghot_quanpin.dict.yaml"

        dyhot_file.write_text(
            "## 2026-08-23 {\n热词\tre ci\t100\n## 2026-08-23 }\n", encoding="utf-8"
        )
        sghot_file.write_text(
            "## 2026-08-22 {\n旧词\tjiu ci\t100\n## 2026-08-22 }\n", encoding="utf-8"
        )

        merged = merge_dict_files(
            str(dyhot_file), str(sghot_file), "2026-08-23", ENCODING_QUANPIN
        )
        self.assertTrue(merged)
        content = sghot_file.read_text(encoding="utf-8")
        self.assertIn("热词\tre ci\t100", content)
        self.assertIn("旧词\tjiu ci\t100", content)


if __name__ == "__main__":
    unittest.main()
