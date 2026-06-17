#!/usr/bin/env python3
"""Stdio MCP server for the million-scale AI content selection engine."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "select_biweekly_highlights.py"
PROTOCOL_VERSION = "2025-06-18"


def text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "name": "select_highlights",
            "description": "Run the local selector on one or more local datasets and generate quality content plus recommendation feature outputs without loading raw rows into model context.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "inputs": {"type": "array", "items": {"type": "string"}, "description": "Input .xlsx paths."},
                    "output_prefix": {"type": "string"},
                    "date_label": {"type": "string"},
                    "workdir": {"type": "string", "default": "./outputs"},
                    "formal_count": {"type": "integer", "default": 30},
                    "candidate_count": {"type": "integer", "default": 10},
                    "preferences": {"type": "array", "items": {"type": "string"}, "description": "Preference topics such as US stocks, AI storage, or Crypto."},
                },
                "required": ["inputs", "output_prefix"],
            },
        },
        {
            "name": "inspect_summary",
            "description": "Read a generated *_summary.md file for safe post-run inspection.",
            "inputSchema": {
                "type": "object",
                "properties": {"summary_path": {"type": "string"}},
                "required": ["summary_path"],
            },
        },
        {
            "name": "validate_outputs",
            "description": "Validate the expected output files and test that generated .xlsx workbooks are valid zip packages.",
            "inputSchema": {
                "type": "object",
                "properties": {"output_prefix": {"type": "string"}, "workdir": {"type": "string", "default": "./outputs"}},
                "required": ["output_prefix"],
            },
        },
        {
            "name": "preview_scored_csv",
            "description": "Preview top rows from a generated CSV artifact without opening the raw export.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "csv_path": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["csv_path"],
            },
        },
    ]


def resolve_safe(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def select_highlights(args: dict[str, Any]) -> dict[str, Any]:
    inputs = args.get("inputs") or []
    if not inputs:
        raise ValueError("inputs is required.")
    command = [
        sys.executable,
        str(SCRIPT),
        *sum([["--input", str(resolve_safe(item))] for item in inputs], []),
        "--output-prefix",
        str(args["output_prefix"]),
        "--workdir",
        str(resolve_safe(args.get("workdir", "./outputs"))),
    ]
    if args.get("date_label"):
        command.extend(["--date-label", str(args["date_label"])])
    if args.get("formal_count") is not None:
        command.extend(["--formal-count", str(args["formal_count"])])
    if args.get("candidate_count") is not None:
        command.extend(["--candidate-count", str(args["candidate_count"])])
    for preference in args.get("preferences") or []:
        command.extend(["--preference", str(preference)])
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return text_result(result.stdout.strip())


def inspect_summary(args: dict[str, Any]) -> dict[str, Any]:
    path = resolve_safe(args["summary_path"])
    return text_result(path.read_text(encoding="utf-8"))


def validate_outputs(args: dict[str, Any]) -> dict[str, Any]:
    workdir = resolve_safe(args.get("workdir", "./outputs"))
    prefix = args["output_prefix"]
    expected = [
        f"{prefix}_quality_content.xlsx",
        f"{prefix}_summary.md",
        f"{prefix}_quality_content.csv",
        f"{prefix}_recommendation_features.csv",
        f"{prefix}_all_scored.csv",
    ]
    lines = []
    for name in expected:
        path = workdir / name
        if not path.exists():
            lines.append(f"missing: {path}")
            continue
        if path.suffix == ".xlsx":
            with zipfile.ZipFile(path) as archive:
                bad = archive.testzip()
            lines.append(f"{name}: {'bad member ' + bad if bad else 'xlsx ok'}")
        else:
            lines.append(f"{name}: ok")
    return text_result("\n".join(lines))


def preview_scored_csv(args: dict[str, Any]) -> dict[str, Any]:
    path = resolve_safe(args["csv_path"])
    limit = int(args.get("limit", 10))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))[:limit]
    return text_result(json.dumps(rows, ensure_ascii=False, indent=2))


TOOLS = {
    "select_highlights": select_highlights,
    "inspect_summary": inspect_summary,
    "validate_outputs": validate_outputs,
    "preview_scored_csv": preview_scored_csv,
}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")
    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "million-scale-content-selector", "version": "0.2.0"},
            }
        elif method == "tools/list":
            result = {"tools": tool_schema()}
        elif method == "tools/call":
            params = message.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in TOOLS:
                raise ValueError(f"Unknown tool: {name}")
            result = TOOLS[name](arguments)
        elif method and method.startswith("notifications/"):
            return None
        else:
            raise ValueError(f"Unsupported method: {method}")
        return {"jsonrpc": "2.0", "id": message_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": message_id, "error": {"code": -32000, "message": str(exc)}}


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle(json.loads(line))
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
