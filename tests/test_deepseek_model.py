import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/python"))

from deepseek_model import rank_deepseek_pro_model, select_best_pro_model


class DeepSeekModelTest(unittest.TestCase):
    def test_prefers_higher_versioned_pro_model(self):
        self.assertEqual(
            select_best_pro_model(
                ["deepseek-v3-pro", "deepseek-v4-flash", "deepseek-v4-pro"]
            ),
            "deepseek-v4-pro",
        )

    def test_prefers_plain_versioned_pro_over_variant(self):
        self.assertEqual(
            select_best_pro_model(["deepseek-v5-preview-pro", "deepseek-v5-pro"]),
            "deepseek-v5-pro",
        )

    def test_rejects_when_no_pro_model_exists(self):
        with self.assertRaises(ValueError):
            select_best_pro_model(["deepseek-v4-flash", "deepseek-chat"])

    def test_rank_non_pro_model_as_zero(self):
        self.assertEqual(rank_deepseek_pro_model("deepseek-v4-flash")[0], 0)


if __name__ == "__main__":
    unittest.main()
