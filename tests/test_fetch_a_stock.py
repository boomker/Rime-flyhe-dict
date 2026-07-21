import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/python"))

from fetch_a_stock import (  # noqa: E402
    DictRecord,
    OUTPUT_PATH,
    PROJECT_ROOT,
    StockName,
    build_dict_records,
    get_pinyin,
    merge_stock_sources,
    normalize_stock_name,
    record_sort_key,
    render_record,
    resolve_output_name,
)


class FetchAStockTest(unittest.TestCase):
    def test_normalize_fullwidth_and_whitespace(self):
        self.assertEqual(normalize_stock_name("万  科Ａ"), "万科A")

    def test_tcl_prefix_is_kept_in_code(self):
        self.assertEqual(get_pinyin("TCL中环"), "TCL vs hr")

    def test_single_letter_uppercase_prefix_is_kept(self):
        self.assertEqual(get_pinyin("S佳通"), "S jx ts")

    def test_st_records_are_commented(self):
        record = DictRecord(name="ST星源", code="000005", flypy="xk yr", commented=True)
        self.assertEqual(render_record(record), "# ST星源\txk yr\t100")

    def test_uppercase_marker_uses_exchange_full_name(self):
        stock = StockName(code="600958", name="XD东方证")
        resolved = resolve_output_name(stock, {"600958": "东方证券"})
        self.assertEqual(resolved, "东方证券")

    def test_xd_name_uses_exchange_company_short_name_before_stripping_marker(self):
        stock = StockName(code="600150", name="XD中国船")
        resolved = resolve_output_name(stock, {"600150": "中国船舶"})
        self.assertEqual(resolved, "中国船舶")

    def test_s_prefix_name_is_not_stripped(self):
        stock = StockName(code="600182", name="S佳通")
        resolved = resolve_output_name(stock, {"600182": "S佳通"})
        self.assertEqual(resolved, "S佳通")

    def test_trade_marker_suffix_is_removed(self):
        stock = StockName(code="688606", name="大普微-UW")
        resolved = resolve_output_name(stock, {})
        self.assertEqual(resolved, "大普微")

    def test_wd_suffix_is_removed_for_ninebot(self):
        stock = StockName(code="689009", name="九号公司-WD")
        resolved = resolve_output_name(stock, {})
        self.assertEqual(resolved, "九号公司")

    def test_exchange_only_stock_is_merged_into_records(self):
        records = build_dict_records(
            merge_stock_sources(
                [StockName(code="600958", name="XD东方证")],
                [
                    StockName(code="600958", name="东方证券"),
                    StockName(code="689009", name="九号公司-WD"),
                ],
            ),
            {"600958": "东方证券", "689009": "九号公司-WD"},
        )
        self.assertIn("九号公司", [record.name for record in records])

    def test_build_dict_records_groups_a_suffix_after_st(self):
        records = build_dict_records(
            [
                StockName(code="000001", name="浦发银行"),
                StockName(code="000002", name="ST平安"),
                StockName(code="000003", name="万科A"),
            ],
            {},
        )
        self.assertEqual([r.name for r in records], ["ST平安", "万科A", "浦发银行"])
        self.assertTrue(records[0].commented)
        self.assertEqual(render_record(records[1]), "万科A\twj ke\t100")

    def test_record_sort_key(self):
        self.assertLess(
            record_sort_key(DictRecord(name="ST平安", code="000002", flypy="st", commented=True)),
            record_sort_key(DictRecord(name="万科A", code="000003", flypy="wk", commented=False)),
        )
        self.assertLess(
            record_sort_key(DictRecord(name="万科A", code="000003", flypy="wk", commented=False)),
            record_sort_key(DictRecord(name="浦发银行", code="000001", flypy="pf", commented=False)),
        )

    def test_output_path_points_to_root_flypy_stock(self):
        self.assertEqual(OUTPUT_PATH, PROJECT_ROOT / "flypy_stock.dict.yaml")


if __name__ == "__main__":
    unittest.main()
