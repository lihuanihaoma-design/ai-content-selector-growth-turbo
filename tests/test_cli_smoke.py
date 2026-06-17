import csv
import importlib.util
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "select_biweekly_highlights.py"
MCP_SCRIPT = ROOT / "mcp" / "content_highlights_server.py"


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
                    "--candidate-count",
                    "1",
                ],
                check=True,
                cwd=ROOT,
            )

            expected = [
                tmp_path / f"{prefix}_quality_content.xlsx",
                tmp_path / f"{prefix}_summary.md",
                tmp_path / f"{prefix}_quality_content.csv",
                tmp_path / f"{prefix}_recommendation_features.csv",
                tmp_path / f"{prefix}_all_scored.csv",
            ]
            for path in expected:
                self.assertTrue(path.exists(), path)

            with (tmp_path / f"{prefix}_quality_content.csv").open(encoding="utf-8-sig", newline="") as handle:
                quality = list(csv.DictReader(handle))
            self.assertEqual(len(quality), 3)
            self.assertIn("UID", quality[0])
            self.assertIn("nickname", quality[0])
            self.assertIn("followers", quality[0])
            self.assertIn("content_url", quality[0])
            self.assertIn("quality_reason", quality[0])
            self.assertIn("comment", quality[0])
            self.assertIn("summary", quality[0])

            with (tmp_path / f"{prefix}_recommendation_features.csv").open(encoding="utf-8-sig", newline="") as handle:
                features = list(csv.DictReader(handle))
            self.assertIn("topic_tags", features[0])
            self.assertIn("ranking_features_json", features[0])
            self.assertIn(features[0]["star_rating"], {"一星", "二星", "三星"})

            with zipfile.ZipFile(tmp_path / f"{prefix}_quality_content.xlsx") as archive:
                sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("star_rating", sheet)
            self.assertIn("123450", sheet)

    def test_defaults_are_public_safe(self):
        help_text = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=True,
            cwd=ROOT,
            text=True,
            capture_output=True,
        ).stdout
        self.assertIn("--preference", help_text)
        self.assertIn("--candidate-count", help_text)

    def test_mcp_tools_list(self):
        request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}) + "\n"
        result = subprocess.run(
            [sys.executable, str(MCP_SCRIPT)],
            input=request,
            text=True,
            capture_output=True,
            cwd=ROOT,
            check=True,
        )
        payload = json.loads(result.stdout.strip())
        names = {tool["name"] for tool in payload["result"]["tools"]}
        self.assertGreaterEqual(
            names,
            {"select_highlights", "inspect_summary", "validate_outputs", "preview_scored_csv"},
        )


if __name__ == "__main__":
    unittest.main()
