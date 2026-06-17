#!/usr/bin/env python3
"""Select high-value content from large-scale local content datasets."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import sys
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

PRIMARY_THEMES = {
    "原油": ["原油", "oil", "crude", "wti", "brent", "opec"],
    "贵金属": ["贵金属", "黄金", "白银", "gold", "silver", "precious metal"],
    "美股": ["美股", "nasdaq", "s&p", "spx", "dow", "nvidia", "tesla", "apple", "us stock"],
    "宏观": ["宏观", "cpi", "fomc", "fed", "利率", "降息", "加息", "通胀", "美元", "macro"],
}
SECONDARY_THEMES = {
    "crypto market": ["crypto market", "market", "行情", "大盘", "btc", "eth", "比特币", "以太坊"],
    "on-chain": ["on-chain", "onchain", "链上", "链上数据"],
    "project research": ["project research", "项目研究", "项目分析", "research", "研报"],
    "DeFi": ["defi", "dex", "staking", "lending", "借贷", "质押"],
    "ETF": ["etf", "spot etf", "现货etf"],
}
LOW_QUALITY_MARKERS = [
    "test",
    "测试",
    "转发",
    "转载",
    "复制",
    "airdrop",
    "giveaway",
    "抽奖",
    "关注点赞",
    "follow me",
]


@dataclass
class Article:
    source_file: str
    source_row: int
    raw: dict[str, str]
    uid: str
    author: str
    follower_count: float
    content_url: str
    content_type: str
    title: str
    content: str
    engagement: float
    content_length: int
    primary_themes: list[str] = field(default_factory=list)
    secondary_themes: list[str] = field(default_factory=list)
    preference_themes: list[str] = field(default_factory=list)
    score: float = 0.0
    pool: str = "excluded"
    status: str = "excluded"
    reason: str = ""


def col_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + ord(ch) - ord("A") + 1
    return index - 1


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    values: list[str] = []
    for si in root.findall(f"{NS_MAIN}si"):
        parts = []
        for text in si.iter(f"{NS_MAIN}t"):
            parts.append(text.text or "")
        values.append("".join(parts))
    return values


def first_sheet_path(zf: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    sheets = workbook.find(f"{NS_MAIN}sheets")
    if sheets is None or not list(sheets):
        raise ValueError("Workbook has no sheets.")
    first_sheet = list(sheets)[0]
    rel_id = first_sheet.attrib.get(f"{NS_REL}id")
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall(f"{NS_PACKAGE_REL}Relationship"):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            return target
    raise ValueError("Could not locate first worksheet.")


def read_cell(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{NS_MAIN}is")
        if inline is None:
            return ""
        return "".join(text.text or "" for text in inline.iter(f"{NS_MAIN}t"))
    value = cell.find(f"{NS_MAIN}v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def read_xlsx(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with zipfile.ZipFile(path) as zf:
        shared_strings = read_shared_strings(zf)
        sheet_path = first_sheet_path(zf)
        root = ET.fromstring(zf.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(f".//{NS_MAIN}row"):
        values: dict[int, str] = {}
        max_index = -1
        for cell in row.findall(f"{NS_MAIN}c"):
            ref = cell.attrib.get("r", "")
            index = col_to_index(ref) if ref else max_index + 1
            values[index] = read_cell(cell, shared_strings)
            max_index = max(max_index, index)
        rows.append([values.get(i, "") for i in range(max_index + 1)])
    if not rows:
        return [], []
    headers = [clean_header(value) or f"column_{i + 1}" for i, value in enumerate(rows[0])]
    records = []
    for values in rows[1:]:
        record = {headers[i]: values[i] if i < len(values) else "" for i in range(len(headers))}
        if any(str(value).strip() for value in record.values()):
            records.append(record)
    return headers, records


def clean_header(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_key(value: str) -> str:
    return re.sub(r"[\s_\-./()（）【】\[\]:：]+", "", value.lower())


def pick(record: dict[str, str], candidates: Iterable[str]) -> str:
    by_key = {normalize_key(key): value for key, value in record.items()}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key in by_key:
            return str(by_key[key]).strip()
    for raw_key, value in record.items():
        normalized = normalize_key(raw_key)
        if any(normalize_key(candidate) in normalized for candidate in candidates):
            return str(value).strip()
    return ""


def normalize_uid(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace(",", "")
    try:
        decimal = Decimal(text)
    except InvalidOperation:
        return text
    if decimal == decimal.to_integral_value():
        return str(decimal.quantize(Decimal(1)))
    return format(decimal.normalize(), "f")


def is_chinese_name(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def parse_number(value: str) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def detect_themes(text: str, themes: dict[str, list[str]]) -> list[str]:
    lower = text.lower()
    found = []
    for theme, keywords in themes.items():
        if any(keyword.lower() in lower for keyword in keywords):
            found.append(theme)
    return found


def low_quality(article: Article) -> bool:
    text = f"{article.title}\n{article.content}".lower()
    if article.content_length < 100:
        return True
    if any(marker.lower() in text for marker in LOW_QUALITY_MARKERS):
        return True
    return False


def build_preference_themes(preferences: list[str]) -> dict[str, list[str]]:
    return {value: [value] for value in preferences if value.strip()}


def star_rating(score: float) -> str:
    if score >= 48:
        return "三星"
    if score >= 28:
        return "二星"
    return "一星"


def summarize_text(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def length_bucket(length: int) -> str:
    if length >= 1200:
        return "long"
    if length >= 400:
        return "medium"
    return "short"


def quality_reason(article: Article) -> str:
    reasons = []
    if article.preference_themes:
        reasons.append("命中用户偏好主题")
    if article.primary_themes:
        reasons.append("具备核心主题相关性")
    if article.content_length >= 400:
        reasons.append("内容信息量较高")
    if article.engagement > 0:
        reasons.append("已有互动信号支撑")
    return "；".join(reasons) or "通过基础质量过滤"


def ai_comment(article: Article) -> str:
    tags = "、".join(article.preference_themes + article.primary_themes + article.secondary_themes) or "泛内容"
    return f"{star_rating(article.score)}内容，适合进入{article.status}；标签：{tags}。"


def build_article(record: dict[str, str], source_file: str, source_row: int, preference_themes: dict[str, list[str]]) -> Article:
    title = pick(record, ["title", "标题", "文章标题", "内容标题"])
    content = pick(record, ["content", "正文", "内容", "文章内容", "post content", "body"])
    author = pick(record, ["author", "作者", "创作者", "昵称", "username", "user name"])
    uid = normalize_uid(pick(record, ["uid", "UID", "用户ID", "user id", "author uid"]))
    follower_count = parse_number(pick(record, ["followers", "follower_count", "粉丝量", "粉丝数", "fans", "fans count"]))
    content_url = pick(record, ["url", "content url", "content_url", "link", "链接", "内容链接", "文章链接"])
    content_type = pick(record, ["type", "类型", "内容类型", "文章类型", "post type"]) or "文章"
    engagement = sum(
        parse_number(pick(record, names))
        for names in [
            ["likes", "like", "点赞", "点赞数"],
            ["comments", "comment", "评论", "评论数"],
            ["shares", "share", "分享", "转发"],
            ["views", "view", "浏览", "阅读", "曝光"],
        ]
    )
    text = f"{title}\n{content}"
    article = Article(
        source_file=source_file,
        source_row=source_row,
        raw=record,
        uid=uid,
        author=author,
        follower_count=follower_count,
        content_url=content_url,
        content_type=content_type,
        title=title,
        content=content,
        engagement=engagement,
        content_length=len(content.strip()),
    )
    article.primary_themes = detect_themes(text, PRIMARY_THEMES)
    article.secondary_themes = detect_themes(text, SECONDARY_THEMES)
    article.preference_themes = detect_themes(text, preference_themes)
    is_article = "文章" in content_type or content_type.lower() in {"article", "post"}
    is_dynamic = "动态" in content_type or content_type.lower() in {"dynamic", "short", "update"}
    if low_quality(article):
        article.pool = "excluded"
        article.reason = "Excluded: short content or low-quality marker."
    elif is_article:
        article.pool = "main"
        article.reason = "Formal content pool candidate."
    elif is_dynamic and (article.primary_themes or article.secondary_themes) and article.content_length >= 180:
        article.pool = "supplemental"
        article.reason = "Supplemental candidate pool."
    else:
        article.pool = "excluded"
        article.reason = "Excluded: unsupported content type."
    engagement_score = min(math.log1p(max(article.engagement, 0)), 6)
    article.score = (
        article.content_length / 120
        + len(article.preference_themes) * 18
        + len(article.primary_themes) * 12
        + len(article.secondary_themes) * 5
        + engagement_score
    )
    if article.pool == "supplemental":
        article.score -= 8
    return article


def select_articles(
    articles: list[Article],
    formal_count: int,
    reserve_count: int,
    target_focus_count: int,
    max_dynamic_formal: int,
    max_dynamic_reserve: int,
) -> tuple[list[Article], list[Article]]:
    eligible = [a for a in articles if a.pool in {"main", "supplemental"} and a.author]
    main = sorted([a for a in eligible if a.pool == "main"], key=sort_key)
    supplemental = sorted([a for a in eligible if a.pool == "supplemental"], key=sort_key)
    selected: list[Article] = []
    def take(article: Article, status: str) -> None:
        selected.append(article)
        article.status = status

    focus_main = [a for a in main if a.primary_themes]
    other_main = [a for a in main if not a.primary_themes]
    for article in focus_main:
        if len(selected) >= min(target_focus_count, formal_count):
            break
        take(article, "formal")
    for article in main:
        if len(selected) >= formal_count:
            break
        take(article, "formal")
    dynamic_count = 0
    for article in supplemental:
        if len(selected) >= formal_count or dynamic_count >= max_dynamic_formal:
            break
        take(article, "formal")
        dynamic_count += 1

    formal = selected[:formal_count]
    reserve: list[Article] = []
    dynamic_reserve = 0
    for article in other_main + focus_main + supplemental:
        if len(reserve) >= reserve_count:
            break
        if article in formal:
            continue
        if article.pool == "supplemental" and dynamic_reserve >= max_dynamic_reserve:
            continue
        article.status = "candidate"
        reserve.append(article)
        if article.pool == "supplemental":
            dynamic_reserve += 1
    for article in articles:
        if article.status == "excluded" and article.pool in {"main", "supplemental"}:
            article.reason = "Not selected after ranking and pool limits."
    return formal, reserve


def sort_key(article: Article) -> tuple[float, int, float, str]:
    return (-article.score, -len(article.primary_themes), -article.engagement, article.author)


def article_row(article: Article) -> dict[str, str | int | float]:
    return {
        "status": article.status,
        "pool": article.pool,
        "score": round(article.score, 3),
        "uid": article.uid,
        "author": article.author,
        "follower_count": round(article.follower_count, 3),
        "content_url": article.content_url,
        "type": article.content_type,
        "title": article.title,
        "content_length": article.content_length,
        "tags": "; ".join(article.preference_themes + article.primary_themes + article.secondary_themes),
        "star_rating": star_rating(article.score),
        "preference_themes": "; ".join(article.preference_themes),
        "primary_themes": "; ".join(article.primary_themes),
        "secondary_themes": "; ".join(article.secondary_themes),
        "engagement": round(article.engagement, 3),
        "quality_reason": quality_reason(article),
        "comment": ai_comment(article),
        "summary": summarize_text(article.content),
        "source_file": article.source_file,
        "source_row": article.source_row,
        "reason": article.reason,
    }


def quality_content_row(article: Article) -> dict[str, str | int | float]:
    return {
        "UID": article.uid,
        "nickname": article.author,
        "followers": round(article.follower_count, 3),
        "content_url": article.content_url,
        "title": article.title,
        "pool": article.status,
        "star_rating": star_rating(article.score),
        "quality_score": round(article.score, 3),
        "quality_reason": quality_reason(article),
        "comment": ai_comment(article),
        "summary": summarize_text(article.content),
    }


def recommendation_feature_row(article: Article, date_label: str) -> dict[str, str | int | float]:
    tags = article.preference_themes + article.primary_themes + article.secondary_themes
    return {
        "item_id": article.content_url or f"{article.source_file}:{article.source_row}",
        "content_url": article.content_url,
        "creator_id": article.uid,
        "creator_nickname": article.author,
        "creator_followers": round(article.follower_count, 3),
        "content_type": article.content_type,
        "title": article.title,
        "summary": summarize_text(article.content),
        "topic_tags": "|".join(tags),
        "preference_tags": "|".join(article.preference_themes),
        "quality_score": round(article.score, 3),
        "star_rating": star_rating(article.score),
        "engagement_score": round(article.engagement, 3),
        "content_length": article.content_length,
        "content_length_bucket": length_bucket(article.content_length),
        "candidate_pool": article.status,
        "cold_start_candidate": "true" if article.status == "formal" and star_rating(article.score) in {"二星", "三星"} else "false",
        "distribution_goal": "growth_seed" if article.preference_themes else "quality_recall",
        "retrieval_keywords": "|".join(tags + [article.title]),
        "context_date_label": date_label,
        "ranking_features_json": json.dumps(
            {
                "quality_score": round(article.score, 3),
                "engagement_score": round(article.engagement, 3),
                "content_length": article.content_length,
                "creator_followers": round(article.follower_count, 3),
                "preference_match_count": len(article.preference_themes),
                "topic_match_count": len(article.primary_themes) + len(article.secondary_themes),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }


def write_csv(path: Path, rows: list[dict[str, str | int | float]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def column_name(index: int) -> str:
    result = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def xlsx_cell(ref: str, value: object) -> str:
    text = "" if value is None else str(value)
    escaped = html.escape(text, quote=False)
    return f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>'


def write_xlsx(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_rows = [headers] + rows
    row_xml = []
    for row_index, row in enumerate(sheet_rows, start=1):
        cells = []
        for col_index, value in enumerate(row):
            cells.append(xlsx_cell(f"{column_name(col_index)}{row_index}", value))
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    dimension = f"A1:{column_name(max(len(headers) - 1, 0))}{max(len(sheet_rows), 1)}"
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/><sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": sheet,
        "xl/styles.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            "</styleSheet>"
        ),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>community-highlights</dc:creator></cp:coreProperties>'
        ),
        "docProps/app.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            "<Application>community-highlights</Application></Properties>"
        ),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def load_preferences(args: argparse.Namespace) -> list[str]:
    preferences = [value.strip() for value in args.preference if value.strip()]
    if args.preferences_file:
        path = Path(args.preferences_file)
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                preferences.append(text)
    return preferences


def write_summary(path: Path, args: argparse.Namespace, articles: list[Article], formal: list[Article], reserve: list[Article]) -> None:
    total = len(articles)
    eligible = len([a for a in articles if a.pool in {"main", "supplemental"}])
    focus = len([a for a in formal if a.primary_themes])
    dynamic = len([a for a in formal if a.pool == "supplemental"])
    lines = [
        f"# AI Content Selection Summary",
        "",
        f"- Date label: {args.date_label or 'not provided'}",
        f"- Input files: {len(args.input)}",
        f"- Total rows scored: {total}",
        f"- Eligible rows: {eligible}",
        f"- Formal pool size: {len(formal)}",
        f"- Candidate pool size: {len(reserve)}",
        f"- Formal focus-theme count: {focus}",
        f"- Formal supplemental dynamic count: {dynamic}",
        "",
        "## Formal Pool",
        "",
        "| Rank | Author | UID | Type | Title | Stars | Themes | Score |",
        "| ---: | --- | --- | --- | --- | --- | ---: |",
    ]
    for index, article in enumerate(formal, start=1):
        themes = "; ".join(article.preference_themes + article.primary_themes + article.secondary_themes)
        lines.append(
            f"| {index} | {article.author} | {article.uid} | {article.content_type} | "
            f"{article.title.replace('|', '/')} | {star_rating(article.score)} | {themes} | {article.score:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Engagement is treated as a supporting signal, not the deciding metric.",
            "- Preference themes act as high-priority relevance signals.",
            "- Datasets with more than 100 rows should be processed by this script before any row-level inspection.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select high-value content from large-scale local content datasets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", action="append", required=True, help="Input .xlsx file. Repeat for multiple weeks.")
    parser.add_argument("--output-prefix", required=True, help="Prefix for generated output files.")
    parser.add_argument("--date-label", default="", help="Human-readable date range, for example 6.1-6.14.")
    parser.add_argument("--workdir", default=".", help="Output directory.")
    parser.add_argument("--formal-count", type=int, default=30)
    parser.add_argument("--candidate-count", dest="reserve_count", metavar="CANDIDATE_COUNT", type=int, default=10)
    parser.add_argument("--target-focus-count", type=int, default=22)
    parser.add_argument("--max-dynamic-formal", type=int, default=4)
    parser.add_argument("--max-dynamic-candidate", dest="max_dynamic_reserve", metavar="MAX_DYNAMIC_CANDIDATE", type=int, default=3)
    parser.add_argument("--preference", action="append", default=[], help="Preference topic such as US stocks, AI storage, or Crypto. Repeatable.")
    parser.add_argument("--preferences-file", help="Optional text file with one preference topic per line.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    preference_themes = build_preference_themes(load_preferences(args))
    articles: list[Article] = []
    for input_file in args.input:
        path = Path(input_file)
        headers, records = read_xlsx(path)
        if not headers:
            continue
        for index, record in enumerate(records, start=2):
            articles.append(build_article(record, path.name, index, preference_themes))
    formal, reserve = select_articles(
        articles,
        args.formal_count,
        args.reserve_count,
        args.target_focus_count,
        args.max_dynamic_formal,
        args.max_dynamic_reserve,
    )
    headers = list(article_row(articles[0]).keys()) if articles else [
        "status",
        "pool",
        "score",
        "uid",
        "author",
        "follower_count",
        "content_url",
        "type",
        "title",
        "content_length",
        "tags",
        "star_rating",
        "preference_themes",
        "primary_themes",
        "secondary_themes",
        "engagement",
        "quality_reason",
        "comment",
        "summary",
        "source_file",
        "source_row",
        "reason",
    ]
    all_rows = [article_row(article) for article in sorted(articles, key=sort_key)]
    selected_articles = formal + reserve
    quality_headers = [
        "UID",
        "nickname",
        "followers",
        "content_url",
        "title",
        "pool",
        "star_rating",
        "quality_score",
        "quality_reason",
        "comment",
        "summary",
    ]
    feature_headers = [
        "item_id",
        "content_url",
        "creator_id",
        "creator_nickname",
        "creator_followers",
        "content_type",
        "title",
        "summary",
        "topic_tags",
        "preference_tags",
        "quality_score",
        "star_rating",
        "engagement_score",
        "content_length",
        "content_length_bucket",
        "candidate_pool",
        "cold_start_candidate",
        "distribution_goal",
        "retrieval_keywords",
        "context_date_label",
        "ranking_features_json",
    ]
    quality_rows = [quality_content_row(article) for article in selected_articles]
    feature_rows = [recommendation_feature_row(article, args.date_label) for article in selected_articles]
    prefix = args.output_prefix
    write_csv(workdir / f"{prefix}_all_scored.csv", all_rows, headers)
    write_csv(workdir / f"{prefix}_quality_content.csv", quality_rows, quality_headers)
    write_xlsx(workdir / f"{prefix}_quality_content.xlsx", quality_headers, [[row[h] for h in quality_headers] for row in quality_rows])
    write_csv(workdir / f"{prefix}_recommendation_features.csv", feature_rows, feature_headers)
    write_summary(workdir / f"{prefix}_summary.md", args, articles, formal, reserve)
    print(f"Scored {len(articles)} rows.")
    print(f"Formal pool: {len(formal)}")
    print(f"Candidate pool: {len(reserve)}")
    print(f"Outputs written to: {workdir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
