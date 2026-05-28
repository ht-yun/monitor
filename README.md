# 竹韵舆情 · AI Monitor

基于 [MediaCrawler](MediaCrawler/) 的社媒舆情监控与 GitHub/Gitee 仓库更新监控平台，支持 AI 情感分析、规则告警与多渠道通知。

## 功能概览

| 模块 | 说明 |
|------|------|
| 社媒监控 | 微博、小红书、抖音、B站、知乎等（依赖 MediaCrawler + 平台 Cookie） |
| 仓库监控 | GitHub / Gitee 按**指定分支**或默认分支检测新提交 |
| AI 分析 | 情感、话题、摘要、风险评分（需 OpenAI 兼容 API） |
| 规则引擎 | 关键词、情感、趋势、异常、风险规则；支持规则集绑定 |
| 通知 | 控制台、钉钉、飞书、企微、Slack、Discord、邮件、Webhook、短信（阿里云） |
| Web 控制台 | http://127.0.0.1:8081/ — 创建任务、手动执行、编辑规则集 |

## 快速开始

```powershell
cd D:\aaa\ing\monitor
python -m venv .venv
.\.venv\Scripts\activate
pip install -r ai_monitor/requirements.txt

copy ai_monitor\.env.example ai_monitor\.env
# 编辑 ai_monitor\.env：OPENAI_API_KEY、GITHUB_TOKEN 等

python -m ai_monitor.cli init-db
python -m ai_monitor.cli init-rules
python -m ai_monitor.cli init-joyoung

python -m ai_monitor.cli start --port 8081
```

浏览器打开：**http://127.0.0.1:8081/**（建议使用系统浏览器，而非 IDE 内嵌预览）。

## MediaCrawler 配置

1. 确保 `MediaCrawler` 目录与本项目同级：`monitor/MediaCrawler`
2. 在 MediaCrawler 中按平台配置登录 Cookie（微博、小红书等）
3. 无 Cookie 时社媒任务会返回空数据，仓库监控不受影响

## 常用 CLI

```powershell
# 添加 GitHub 仓库监控（支持完整 URL）
python -m ai_monitor.cli watch-repo add --platform github --repo https://github.com/owner/name
python -m ai_monitor.cli watch-repo add --platform github --repo https://github.com/owner/name/tree/develop
python -m ai_monitor.cli watch-repo add --platform github --repo owner/name --branch develop

# 手动检查仓库
python -m ai_monitor.cli watch-repo check --job-id github_owner_repo

# 后台轮询（仓库 + 已注册定时任务）
python -m ai_monitor.cli daemon

# 导入九阳品牌规则
python -m ai_monitor.cli init-joyoung
```

## 环境变量（`ai_monitor/.env`）

| 变量 | 说明 |
|------|------|
| `AIMONITOR_OPENAI_API_KEY` | AI 分析 |
| `AIMONITOR_GITHUB_TOKEN` | GitHub API |
| `AIMONITOR_GITEE_TOKEN` | Gitee API |
| `AIMONITOR_DINGTALK_WEBHOOK_URL` | 钉钉机器人 |
| `AIMONITOR_FEISHU_WEBHOOK_URL` | 飞书 |
| `AIMONITOR_WECHAT_WORK_WEBHOOK_URL` | 企业微信 |
| `AIMONITOR_SMS_*` + `AIMONITOR_SMS_PHONE_NUMBERS` | 阿里云短信 |

完整列表见 `ai_monitor/.env.example`。

## API 摘要

- `GET /api/jobs` — 任务列表
- `POST /api/jobs` — 创建社媒/仓库任务
- `PATCH /api/jobs/{id}` — 编辑关键词、状态、规则集
- `POST /api/jobs/{id}/run` — 手动执行
- `GET /api/system/status` — 运行环境检测
- `POST /api/rules/import-default` — 导入默认规则

## 项目结构

```
monitor/
├── MediaCrawler/          # 爬虫（需单独配置）
├── ai_monitor/
│   ├── main.py            # FastAPI 入口
│   ├── cli.py             # 命令行
│   ├── workflow/          # 社媒流水线
│   ├── repo_watch/        # 仓库监控
│   ├── rules/             # 规则引擎
│   └── static/            # Web 前端
└── README.md
```

## 分支监控说明

- **留空分支**：跟踪仓库**默认分支**（GitHub 上多为 `main`）
- **填写分支名**：仅当该分支有新提交时告警（如 `develop`、`release/v1`）
- 同一仓库可创建多个任务监控不同分支（`job_id` 会带分支后缀，如 `github_owner_repo__develop`）
- 修改任务分支后会重新建立基线（避免误报）

## 说明

- 数据库时间存 UTC，前端显示为北京时间 (UTC+8)
- 拼多多无官方爬虫；可通过关键词「拼多多」在社媒内容中间接监控
- 生产环境请修改 `AIMONITOR_DASHBOARD_SECRET_KEY` 并轮换已泄露的 Token
