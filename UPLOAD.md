# 发布前检查清单

这个仓库可以公开展示，但真实业务数据不能进仓库。

发布、提交、推送前逐项检查：

1. 不上传真实内容池。
2. 不上传生成的正式池、候选池和评分表。
3. 不上传私有偏好主题文件。
4. 不上传本地个人路径。
5. 不上传密钥、Cookie、Token、`.env`。
6. 不在 README、Skill、代码注释里写任何组织名、产品名或个人身份信息。

建议验证：

```bash
python3 -m py_compile scripts/select_biweekly_highlights.py
python3 scripts/select_biweekly_highlights.py --help
python3 -m unittest discover -s tests
```

生成结果建议放在被忽略的目录：

```bash
python3 scripts/select_biweekly_highlights.py \
  --input input/local_content_pool.xlsx \
  --output-prefix growth_content_pool_YYYY-MM-DD \
  --date-label M.D-M.D \
  --workdir ./outputs \
  --preference 美股 \
  --preference Crypto
```

`input/` 和 `outputs/` 默认不会进入 Git。
