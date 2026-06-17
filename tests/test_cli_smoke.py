import csv
import importlib.util
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "select_biweekly_highlights.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("select_biweekly_highlights", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CliSmokeTest(unittest.TestCase):
    def test_cli_generates_expected_outputs(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tool = load_tool()
            source = tmp_path / "articles.xlsx"
            rows = [
                {
                    "UID": "1.2345E+5",
                    "作者": "张三",
                    "类型": "文章",
                    "标题": "原油与宏观市场分析",
                    "内容": "原油 贵金属 美股 宏观 " * 25,
                    "点赞": "88",
                    "评论": "12",
                },
                {
                    "UID": "67890",
                    "作者": "Alice",
                    "类型": "文章",
                    "标题": "DeFi project research",
                    "内容": "DeFi ETF on-chain crypto market " * 25,
                    "点赞": "30",
                    "评论": "4",
                },
                {
                    "UID": "99999",
                    "作者": "Bob",
                    "类型": "动态",
                    "标题": "Macro thread",
                    "内容": "宏观 美股 project research " * 30,
                    "点赞": "10",
                    "评论": "2",
                },
            ]
            tool.write_xlsx(source, list(rows[0].keys()), [[row[k] for k in rows[0].keys()] for row in rows])

            prefix = "generated"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(source),
                    "--output-prefix",
                    prefix,
                    "--date-label",
                    "1.1-1.7",
                    "--workdir",
                    str(tmp_path),
                    "--formal-count",
                    "2",
                    "--reserve-count",
                    "1",
                ],
                check=True,
                cwd=ROOT,
            )

            expected = [
                tmp_path / f"{prefix}_formal_list.xlsx",
                tmp_path / f"{prefix}_reward_flow_submit.xlsx",
                tmp_path / f"{prefix}_summary.md",
                tmp_path / f"{prefix}_reserve.csv",
                tmp_path / f"{prefix}_all_scored.csv",
                tmp_path / f"{prefix}_formal.csv",
            ]
            for path in expected:
                self.assertTrue(path.exists(), path)

            with (tmp_path / f"{prefix}_formal.csv").open(encoding="utf-8-sig", newline="") as handle:
                formal = list(csv.DictReader(handle))
            self.assertEqual(len(formal), 2)
            self.assertEqual({row["author"] for row in formal}, {"张三", "Alice"})

            with zipfile.ZipFile(tmp_path / f"{prefix}_reward_flow_submit.xlsx") as archive:
                sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("UID", sheet)
            self.assertIn("currency", sheet)
            self.assertIn("amount", sheet)
            self.assertIn("APPLICATION NUMBER", sheet)
            self.assertIn("123450", sheet)


if __name__ == "__main__":
    unittest.main()
