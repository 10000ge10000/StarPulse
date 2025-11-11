# StarPulse · 详细说明

定时（北京时间每日 0 点与 12 点）抓取 GitHub 项目数据，计算过去一次运行以来 Star 增长，并按“中文项目 / 非中文项目”两大类输出榜单与简要说明。

> 本文件包含项目的完整文档与使用说明；主仓库 `README.md` 仅展示项目简介与每日榜单。

## 功能

- 候选仓库抓取（按主题、语言、最小 star、最近活动）
- 星数据快照（JSON）并计算增量与增长率
- 分类：中文项目 / 非中文项目 + 语言/主题等
- 输出：`output/LATEST.md` 与 `output/latest.json`
- GitHub Actions 定时任务（UTC 4:00 与 16:00 ≈ 北京时间 12:00 与 0:00）

## 运行方式

- 本地运行需要 `GH_TOKEN` 环境变量（GitHub Personal Access Token，最少 `public_repo` 权限）。
- 安装依赖后运行主脚本：

```bash
python -m src.run_all
```

## 在 GitHub Actions 上运行

本项目内置工作流文件 `.github/workflows/refresh.yml`，默认在每天北京时间 0 点与 12 点各运行一次（对应 UTC 16:00 与 04:00）。

前置条件：

1) 仓库需已公开（或私有也可，但 Token 权限需覆盖访问范围）。
2) 在仓库 Settings → Security → Secrets and variables → Actions 中新增一个 Secret：
   - Name：`GH_TOKEN`
   - Value：你的 GitHub Personal Access Token（建议 classic，无 scope 或仅 Metadata 即可；避免多余权限）
3) 确认工作流已启用（Actions 页面显示可运行）。

工作流内容摘要：

- 使用 Python 3.11 安装依赖并运行 `python -m src.run_all`
- 自动生成/更新：`data/snapshots/`、`output/LATEST.md`、`output/latest.json`、并将榜单注入 `README.md`
- 提交变更（若有）并尝试推送回仓库

手动触发：

- 在 Actions 页面选择该工作流，点击“Run workflow”手动执行

更改运行时间（cron）：

- 在 `.github/workflows/refresh.yml` 中修改：

```yaml
on:
  schedule:
    - cron: '0 4,16 * * *' # 北京时间 12:00 与 00:00
```

常见问题：

- 速率限制：若未正确设置 `GH_TOKEN`，请求速率很低，候选仓库较多时可能超时或数据不全。
- 推送失败：分支保护或权限不足时会失败；可仅提交到 artifacts，或使用 PR 方式。
- Token 泄漏：不要把 Token 写入代码库；如怀疑泄漏，请立即撤销并重建。

## 目录结构

```text
src/
  config.py            # 配置项（阈值、分类规则、搜索参数）
  fetch_candidates.py  # 候选仓库搜索与去重
  snapshot_and_diff.py # 快照 + 增量计算（含 README 中文检测）
  categorize_and_render.py # 分类与 Markdown/JSON 输出
  classify_utils.py    # 中文判定工具函数
  run_all.py           # 一键执行入口

data/
  snapshots/           # 时间序列快照（JSON）

output/
  LATEST.md            # 最新榜单（生成）
  latest.json          # 最新结构化数据（生成）

.github/workflows/
  refresh.yml          # 定时任务
```

## 配置

可在 `src/config.py` 中调整：

- 候选搜索关键词、语言白名单、最小 star、候选上限
- 增长率计算的最小基数过滤
- 中文检测规则（topics/描述/README 片段中的中文比例）
- 增量榜数量：`DiffConfig.top_n`
- 增幅榜数量：`DiffConfig.growth_top_n`
- “新项目”窗口天数：`DiffConfig.new_repo_days`
- 趋势窗口快照数：`DiffConfig.trend_history_len`
- 噪声过滤阈值：`DiffConfig.huge_repo_star_threshold` 与 `DiffConfig.min_delta_for_huge`

## 上线 GitHub 的准备清单

- [ ] 仓库创建并推送代码（含 `.github/workflows/refresh.yml`）
- [ ] 在仓库 Secrets 配置 `GH_TOKEN`
- [ ] 首次手动运行工作流，观察 `output/` 与 `README.md` 是否生成榜单
- [ ] 检查提交权限（若分支保护，改为 PR 推送或降低保护策略）
- [ ] 设置仓库描述与 Topics（如：stars, trending, analytics, leaderboard）以提升可发现性
- [ ] 在 README 顶部添加徽章（Actions 状态、Stars、License）可选
- [ ] 关注速率限制与配额，必要时缩小候选范围或启用 GraphQL 批量

## 注意

- 本项目仅基于历史快照计算增长，不与 GitHub Trending 页面直接耦合。
- 速率限制：建议使用 `GH_TOKEN`；如候选量较大，将自动分页与限流。

## 许可

MIT
