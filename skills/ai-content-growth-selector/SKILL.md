---
name: ai-content-growth-selector
description: AI Content Selector and Growth Turbo。面向百万级内容池，根据用户偏好自动筛选、评分、打标，输出优质内容 Excel 和推荐系统特征数据。
---

# AI Content Selector and Growth Turbo

用于内容增长、推荐算法冷启动、爆款内容预判和大规模内容池治理。

## 硬规则

如果内容数据超过 100 行，Agent 不能读取原始行到模型上下文。

必须先运行工具：

```bash
python3 scripts/select_biweekly_highlights.py \
  --input local_content_pool.xlsx \
  --output-prefix growth_turbo_YYYY-MM-DD \
  --date-label M.D-M.D \
  --workdir ./outputs \
  --preference 美股 \
  --preference "AI storage" \
  --preference Crypto \
  --formal-count 50 \
  --candidate-count 100
```

然后只检查生成物：

- `*_summary.md`
- `*_quality_content.csv`
- `*_recommendation_features.csv`
- `*_all_scored.csv`

## Agent 工作流

1. 确认输入路径存在。
2. 收集用户偏好主题，例如美股、AI 存储、Crypto、宏观、DeFi。
3. 运行筛选脚本或 MCP 工具 `select_highlights`。
4. 先读 `*_summary.md`，确认正式池、候选池、星级分布和主题命中。
5. 再读 `*_quality_content.csv`，检查 UID、昵称、粉丝量、内容 URL、优质原因、点评和摘要。
6. 读取 `*_recommendation_features.csv`，确认推荐系统需要的标签和特征维度。
7. 根据 `star_rating`、`topic_tags`、`preference_tags`、`quality_score` 给出复核建议。
8. 如用户需要，提示这些作者或内容可以进入推流、运营触达、激励等后续动作。
9. 只在用户明确要求时抽查少量原始内容。

## 输出契约

核心输出：

- `*_quality_content.xlsx`
- `*_recommendation_features.csv`

辅助输出：

- `*_quality_content.csv`
- `*_all_scored.csv`
- `*_summary.md`

优质内容字段：

- `UID`
- `nickname`
- `followers`
- `content_url`
- `quality_reason`
- `comment`
- `summary`

推荐特征字段：

- `item_id`
- `content_url`
- `creator_id`
- `creator_followers`
- `content_type`
- `topic_tags`
- `preference_tags`
- `quality_score`
- `star_rating`
- `engagement_score`
- `content_length_bucket`
- `candidate_pool`
- `cold_start_candidate`
- `distribution_goal`
- `retrieval_keywords`
- `ranking_features_json`

## 筛选原则

- 用户偏好主题优先。
- 内容质量和信息密度优先。
- 互动数据只是辅助信号。
- 正式池用于推荐或运营复核。
- 候选池用于扩充、二次筛选和调参。
- 星级标签用于快速判断分发优先级。

## MCP 优先

如果 Agent 环境支持 MCP，优先使用：

- `select_highlights`
- `inspect_summary`
- `validate_outputs`
- `preview_scored_csv`
