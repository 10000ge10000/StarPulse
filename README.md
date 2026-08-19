# StarPulse 🚀⭐

> 每日两次（北京时间 00:00 & 12:00）自动抓取候选仓库最新 Star，并与上一快照对比，输出“增量 / 增幅”双榜 + 新项目榜，按中文 / 非中文拆分展示。

[![Blog](https://img.shields.io/badge/Blog-910501.xyz-orange)](https://blog.910501.xyz/)
[![Bilibili](https://img.shields.io/badge/B%E7%AB%99-59438380-00a1d6?logo=bilibili)](https://space.bilibili.com/59438380)
[![YouTube](https://img.shields.io/badge/YouTube-10000%20AI%20Share-ff0000?logo=youtube&logoColor=white)](https://www.youtube.com/channel/UCqgvZnCN9-9pZcL4SWxmnDw)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 项目说明

StarPulse 是一个 GitHub 项目星标增长监控工具，它定时抓取 GitHub 项目数据，计算过去一次运行以来的 Star 增长，并按“中文项目 / 非中文项目”两大类输出榜单与趋势信息。项目旨在帮助用户发现具有潜力的开源项目， particularly 中文项目。

## 特性

- ⏱ 定时自动：GitHub Actions 定时运行，无需人工干预
- 🌓 双指标洞察：绝对增量与相对增幅并行，避免大盘仓库“压榜”
- 🐣 新项目扶持：最近 30 天创建项目单独榜单，发现早期黑马
- 🇨🇳 中文识别：综合描述 / README 采样 / 关键词判定中文项目
- 📈 趋势火花线：30 次历史星数生成迷你 sparkline，直观走势
- 🧹 噪声过滤：超大仓库微小增量（<2）不进入主榜，减少信息噪声

## 快速开始

### 本地运行

```bash
# 安装依赖
pip install PyGithub requests tenacity tabulate PyYAML

# 设置 GitHub Token
export GH_TOKEN="your_github_personal_access_token"

# 运行主脚本
python -m src.run_all
```

### GitHub Actions

本项目内置 `.github/workflows/refresh.yml`，默认在每天北京时间 0 点与 12 点（UTC 16:00 与 04:00）运行一次。

1. 仓库创建并推送代码（含 `.github/workflows/refresh.yml`）
2. 在仓库 Settings → Secrets 配置 `GH_TOKEN`
3. 首次手动运行工作流，观察输出
4. 检查提交权限

## 配置

可在 `src/config.py` 中调整：

- 候选搜索关键词、语言白名单、最小 star、候选上限
- 增长率计算的最小基数过滤
- 中文检测规则（topics/描述/README 片段中的中文比例）
- 增量榜数量：`DiffConfig.top_n`
- 增幅榜数量：`DiffConfig.growth_top_n`
- “新项目”窗口天数：`DiffConfig.new_repo_days` (默认 30)
- 趋势窗口快照数：`DiffConfig.trend_history_len` (默认 30)
- 噪声过滤阈值：`DiffConfig.huge_repo_star_threshold` (默认 100000) 与 `DiffConfig.min_delta_for_huge` (默认 2)
- 首现项目显示数量：`DiffConfig.first_seen_max` (默认 20)

## 部署

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY .github/ /app/.github/

ENV GH_TOKEN=${GH_TOKEN}

CMD ["python", "-m", "src.run_all"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  starpulse:
    build: .
    environment:
      - GH_TOKEN=${GH_TOKEN}
    volumes:
      - ./data:/app/data
      - ./output:/app/output
    restart: unless-stopped
```

## 使用方法

### 查看每日榜单

每日两次（北京时间 00:00 & 12:00）自动生成的 `README.md` 包含当日榜单，包括：

- **星增长榜**：按 Star 增长排序的项目列表
- **增幅榜**：按增长率排序的项目列表  
- **新项目榜**：最近 30 天创建的项目列表
- **中文/非中文分离**：双榜并行展示

### 输出文件

- `output/LATEST.md`：最新 Markdown 格式的榜单
- `output/latest.json`：最新结构化数据
- `data/snapshots/`：历史快照（JSON 格式）

## 常见问题

### Q: 为什么我的仓库没有出现在榜单上？
A: 可能的原因包括：
- 仓库 Star 数未达阈值（默认 MIN_STARS=200）
- 最近一年无活动（pushedat 超过 365 天）
- 被噪声过滤（超大仓库增量 < 2）

### Q: 如何自定义候选仓库搜索？
A: 修改 `src/config.py` 中的 `SearchConfig`：
- 调整 `languages` 语言白名单
- 调整 `topics` 主题白名单
- 修改 `min_stars` 最低星门槛
- 设置 `max_candidates` 候选上限

### Q: GitHub API 速率限制怎么办？
A: 建议设置 `GH_TOKEN`，token 有更高的速率上限。若候选量较大，项目会自动分页和限流。

### Q: 如何修改运行时间？
A: 修改 `.github/workflows/refresh.yml` 中的 cron 表达式：

```yaml
on:
  schedule:
    - cron: '0 4,16 * * *' # 北京时间 12:00 与 00:00
```

## 许可证

MIT

## 致谢

数据来源于 GitHub 公共 API。项目受到以下开源项目的启发：
- GitHub Trending
- LLM 相关工具和库