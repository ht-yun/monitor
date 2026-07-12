# 飞书云文档仓库自动监控优化方案

## 1. 背景与目标

当前 `ai_monitor` 项目已经支持手动创建 GitHub/Gitee 仓库监控任务，并且可以按指定分支检测新提交。下一步优化目标是接入飞书云文档：

- 用户只需要在飞书云文档中添加 GitHub/Gitee 仓库链接。
- 系统自动读取飞书云文档，解析仓库链接。
- 系统自动将仓库加入监控。
- 系统自动拉取该仓库的默认分支和其他分支，并为每个分支建立监控任务。
- 不同仓库要清晰区分，同名仓库但不同 owner 不得混淆。
- 一个仓库下面要能展示主分支和其他分支信息。
- 当远端有人新建分支时，系统能自动发现并加入监控任务。

参考 `D:\aaa\ing\Exhibit` 项目的飞书同步思路，本项目建议采用“飞书作为外部数据源，本地同步入库，再由本地状态驱动业务”的架构，不建议直接把仓库监控逻辑写进 webhook 或前端按钮中。

## 2. 参考项目可复用思路

`Exhibit` 项目中可借鉴的设计包括：

- 使用飞书自建应用的 `App ID` 和 `App Secret` 获取 `tenant_access_token`。
- 使用飞书云文档 `doc_token` 读取文档 blocks。
- 从 blocks JSON 中扫描链接。
- 将飞书数据先同步到本地数据库，再由业务模块消费。
- 提供手动同步接口和定时同步任务。
- webhook 只作为触发器，核心同步逻辑保持幂等、可重复执行。

当前项目应使用 Python 原生实现飞书接入，避免额外引入 Node 服务，保持部署和维护简单。

## 3. 总体架构

建议新增以下模块：

```text
ai_monitor/
  feishu/
    __init__.py
    client.py          # 飞书 token、云文档 blocks 读取
    parser.py          # 从云文档内容中提取 GitHub/Gitee 仓库链接
    sync.py            # 飞书文档 -> 本地仓库源记录
  repo_watch/
    reconciler.py      # 仓库源记录 -> 分支发现 -> MonitoringJob 自动生成
```

核心流程：

```text
飞书云文档
  -> FeishuClient 读取 blocks
  -> RepoLinkParser 提取 GitHub/Gitee 链接
  -> monitored_repositories 入库
  -> GitHub/Gitee API 拉取仓库信息和全部分支
  -> monitored_branches 入库
  -> monitoring_jobs 自动创建或更新
  -> 现有 JobRunner 按分支检测新提交
```

## 4. 数据模型设计

现有 `monitoring_jobs` 表适合表示单个执行任务，但不适合表达“仓库 -> 多分支”的父子关系。建议新增两张表。

### 4.1 monitored_repositories

用于表示一个被监控的仓库。

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer | 主键 |
| platform | String | `github` 或 `gitee` |
| owner | String | 仓库 owner |
| name | String | 仓库名 |
| repo | String | `owner/name` |
| repo_url | String | 仓库主页 URL |
| default_branch | String | 默认分支 |
| source | String | `feishu_doc` 或 `manual` |
| source_doc_token | String | 来源飞书文档 token |
| first_seen_at | DateTime | 首次发现时间 |
| last_seen_at | DateTime | 最近在飞书中出现时间 |
| last_branch_sync_at | DateTime | 最近分支同步时间 |
| status | String | `active`、`missing_from_feishu`、`error` |
| error_message | Text | 最近错误 |

唯一约束：

```text
platform + repo
```

### 4.2 monitored_branches

用于表示仓库下的每个分支。

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer | 主键 |
| repository_id | Integer | 关联 `monitored_repositories.id` |
| branch | String | 分支名 |
| is_default | Boolean | 是否默认分支 |
| job_id | String | 对应 `monitoring_jobs.job_id` |
| last_sha | String | 最近 commit SHA |
| last_commit_author | String | 最近提交人 |
| last_commit_at | DateTime | 最近提交时间 |
| first_seen_at | DateTime | 首次发现时间 |
| last_seen_at | DateTime | 最近远端存在时间 |
| status | String | `active`、`deleted`、`paused` |

唯一约束：

```text
repository_id + branch
```

### 4.3 与现有 monitoring_jobs 的关系

`monitoring_jobs` 继续作为任务执行表。每个仓库分支对应一条 `monitoring_jobs` 记录。

建议所有分支都显式写入 `branch` 字段，包括默认分支。这样前端展示和任务定位更清晰。

## 5. 仓库链接解析要求

需要支持以下格式：

```text
https://github.com/owner/repo
https://github.com/owner/repo.git
https://github.com/owner/repo/tree/main
https://github.com/owner/repo/tree/release/v1
https://github.com/owner/repo/blob/main/path/to/file
git@github.com:owner/repo.git
https://gitee.com/owner/repo
https://gitee.com/owner/repo/tree/develop
gitee.com/owner/repo
owner/repo
```

执行要求：

- 从飞书文档任意文本或链接字段中批量提取仓库 URL。
- 如果 URL 指向具体分支，仍应按仓库入库，并通过远端 API 拉取该仓库全部分支。
- 清理 `.git` 后缀。
- 分支名允许包含 `/`。
- 同名仓库但不同 owner 必须区分。
- 同一仓库在飞书文档中出现多次时，不得重复创建仓库或任务。

## 6. 分支发现要求

需要扩展 GitHub/Gitee collector。

GitHub collector 增加：

```text
fetch_repo_info(repo) -> default_branch, repo_url
list_branches(repo) -> branch list
```

Gitee collector 增加：

```text
fetch_repo_info(repo) -> default_branch, repo_url
list_branches(repo) -> branch list
```

执行要求：

- 分页拉取所有分支。
- 拉取失败时记录到 `monitored_repositories.error_message`。
- 新发现分支时自动创建 `monitored_branches` 和对应 `monitoring_jobs`。
- 新分支首次加入时只建立 baseline，不直接发送“新提交”告警。
- 可选发送“发现新分支”通知。
- 远端分支删除后，本地标记为 `deleted` 或暂停对应任务，不直接删除历史记录。

## 7. Job ID 生成要求

当前项目的 job_id 基础格式为：

```text
github_owner_repo
github_owner_repo__develop
```

建议升级为更稳定的格式：

```text
{platform}_{owner}_{repo}__{branch_slug}__{hash8}
```

示例：

```text
github_openai_codex__main__a1b2c3d4
github_openai_codex__release_v1__f6e7d8c9
```

执行要求：

- `branch_slug` 只用于可读性。
- `hash8` 基于原始 `platform + repo + branch` 生成，避免分支名下划线和斜杠造成冲突。
- 历史任务兼容旧 job_id，不强制迁移。
- 新建任务统一使用新格式。

## 8. 配置项设计

在 `ai_monitor/config/settings.py` 中新增：

```text
AIMONITOR_FEISHU_APP_ID=
AIMONITOR_FEISHU_APP_SECRET=
AIMONITOR_FEISHU_REPO_DOC_TOKEN=
AIMONITOR_FEISHU_VERIFICATION_TOKEN=
AIMONITOR_FEISHU_SYNC_INTERVAL_SECONDS=600
AIMONITOR_REPO_BRANCH_SYNC_INTERVAL_SECONDS=1800
```

执行要求：

- 所有密钥只能通过 `.env` 或环境变量配置。
- 不得把 App Secret、token、访问密钥写入代码。
- 系统状态接口需要展示飞书配置是否完整，但不得返回密钥明文。

## 9. API 与 CLI 设计

### 9.1 CLI

新增命令：

```powershell
python -m ai_monitor.cli feishu sync
python -m ai_monitor.cli repo reconcile
python -m ai_monitor.cli repo branches --repo owner/name --platform github
```

命令含义：

- `feishu sync`：读取飞书云文档，发现仓库链接并入库。
- `repo reconcile`：对已发现仓库拉取分支，并生成监控任务。
- `repo branches`：调试用，查看远端仓库分支列表。

### 9.2 FastAPI

新增接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/feishu/sync` | 手动触发飞书同步 |
| GET | `/api/feishu/status` | 查看飞书同步状态 |
| POST | `/api/repositories/reconcile` | 手动触发仓库分支 reconcile |
| GET | `/api/repositories` | 仓库列表 |
| GET | `/api/repositories/{id}/branches` | 仓库分支列表 |
| PATCH | `/api/repositories/{id}` | 暂停或恢复整个仓库 |
| PATCH | `/api/repositories/{id}/branches/{branch}` | 暂停或恢复单分支 |

执行要求：

- 手动同步接口必须可重复调用。
- 同步结果应返回新增仓库数、新增分支数、新增任务数、失败列表。
- API 不应阻塞过久，后续可扩展为后台任务。

## 10. 前端优化要求

当前前端任务列表是平铺结构。新增“仓库监控”视图，按仓库分组展示分支。

展示结构：

```text
GitHub / owner/repo
  默认分支: main    last_sha / author / commit_at / status
  develop          last_sha / author / commit_at / status
  release/v1       last_sha / author / commit_at / status
```

执行要求：

- 仓库层展示平台、仓库名、来源、默认分支、分支数量、最后同步时间。
- 分支层展示分支名、状态、最近 SHA、最近提交人、最近提交时间、对应 job 状态。
- 支持手动触发“同步飞书”和“刷新分支”。
- 支持暂停整个仓库。
- 支持暂停单个分支。
- 不再只用平铺 job 列表表达仓库监控。

## 11. 定时任务设计

建议统一放入 `ai_monitor/daemon/unified.py`。

执行周期建议：

| 任务 | 默认周期 | 说明 |
|---|---:|---|
| 飞书云文档同步 | 10 分钟 | 发现新增仓库链接 |
| 仓库分支 reconcile | 30 分钟 | 发现新增或删除分支 |
| 仓库提交检测 | 60 分钟 | 沿用现有 repo watch |

执行要求：

- 飞书同步、分支发现、提交检测相互独立。
- 任一环节失败不能阻断其他环节。
- 每轮执行都要记录成功/失败状态。
- 同步逻辑必须幂等，重复执行不能重复创建任务。

## 12. 实施步骤

### 阶段一：基础模型和迁移

1. 新增 `MonitoredRepository` ORM 模型。
2. 新增 `MonitoredBranch` ORM 模型。
3. 在 `init_db()` 的轻量迁移中补充新表创建。
4. 为 `platform + repo` 添加唯一约束。
5. 为 `repository_id + branch` 添加唯一约束。

验收要求：

- 启动项目后自动创建新表。
- 重复插入同一仓库不会产生重复记录。
- 重复插入同一仓库分支不会产生重复记录。

### 阶段二：仓库链接解析增强

1. 扩展 `repo_watch/url_parser.py`。
2. 新增批量提取函数，例如 `extract_repo_targets(text)`。
3. 支持 GitHub/Gitee URL、SSH URL、`.git` 后缀、分支 URL。
4. 增加解析测试。

验收要求：

- 能从普通文本和 JSON 字符串中提取多个仓库链接。
- 能正确区分 GitHub/Gitee。
- 能正确处理分支名包含 `/` 的链接。

### 阶段三：GitHub/Gitee 分支发现

1. 扩展 `GitHubCollector`。
2. 扩展 `GiteeCollector`。
3. 新增统一的 `RepoRemoteService` 或在 `reconciler.py` 中分发平台实现。
4. 实现默认分支读取。
5. 实现全量分支列表读取。

验收要求：

- 能获取公开 GitHub 仓库默认分支。
- 能获取公开 GitHub 仓库全部分支。
- 配置 token 后能访问私有或高频请求场景。
- Gitee 同理。

### 阶段四：飞书云文档同步

1. 新增 `ai_monitor/feishu/client.py`。
2. 实现 tenant token 获取与缓存。
3. 实现 docx blocks 分页读取。
4. 新增 `ai_monitor/feishu/parser.py`。
5. 新增 `ai_monitor/feishu/sync.py`。
6. 实现飞书文档仓库链接发现并写入 `monitored_repositories`。

验收要求：

- 配置飞书文档 token 后能读取 blocks。
- 在飞书文档添加仓库链接后，本地能发现并入库。
- 同步接口重复执行不会重复创建仓库。

### 阶段五：仓库 reconcile 与任务自动生成

1. 新增 `ai_monitor/repo_watch/reconciler.py`。
2. 遍历 `monitored_repositories` 中 active 仓库。
3. 拉取默认分支和全部分支。
4. upsert `monitored_branches`。
5. 为每个 active 分支创建或更新 `monitoring_jobs`。
6. 对新任务建立 baseline，避免误报。

验收要求：

- 一个飞书仓库链接可以生成该仓库所有分支监控任务。
- 新建远端分支后，下次 reconcile 自动生成任务。
- 删除远端分支后，本地标记为 deleted 或 paused。
- 不同仓库和不同分支互不覆盖。

### 阶段六：API、CLI 与前端

1. CLI 增加 `feishu sync` 和 `repo reconcile`。
2. FastAPI 增加飞书同步和仓库分组接口。
3. 前端新增仓库分组视图。
4. 系统状态页面展示飞书配置状态。

验收要求：

- 可通过 CLI 手动同步。
- 可通过 Web 手动同步。
- 前端能按仓库分组展示分支。
- 分支状态、最近提交信息展示正确。

### 阶段七：daemon 集成与通知

1. 在统一 daemon 中加入飞书同步周期。
2. 在统一 daemon 中加入分支 reconcile 周期。
3. 新分支发现时可发送通知。
4. 同步失败时记录错误并可在系统状态中展示。

验收要求：

- 后台运行时无需人工点击即可发现新仓库。
- 后台运行时无需人工点击即可发现新分支。
- 单个仓库失败不会影响其他仓库。

## 13. 测试要求

至少覆盖以下测试：

- URL 解析测试。
- 飞书 blocks 链接提取测试。
- GitHub 分支列表解析测试。
- Gitee 分支列表解析测试。
- 仓库 upsert 幂等测试。
- 分支 upsert 幂等测试。
- job_id 冲突测试。
- 新分支自动创建任务测试。
- 删除分支标记测试。
- daemon 单轮执行测试。

建议优先写纯函数和服务层测试，减少对真实飞书和真实 GitHub/Gitee API 的依赖。外部 API 使用 mock response。

## 14. 安全与稳定性要求

- 所有飞书、GitHub、Gitee token 必须通过环境变量配置。
- 不得在日志中输出完整 token。
- 飞书 webhook 如后续启用，必须校验 verification token 或签名。
- 外部 API 请求必须设置 timeout。
- 外部 API 请求失败要记录错误，不应导致 daemon 退出。
- 分支发现和任务生成必须幂等。
- 数据库写入应使用唯一约束兜底，避免并发重复创建。
- 对 API rate limit 要有明确错误提示。

## 15. 推荐优先级

优先做主链路：

```text
飞书云文档扫描
  -> 仓库链接发现
  -> 仓库入库
  -> 分支发现
  -> monitoring_jobs 自动生成
```

第二轮再做：

```text
飞书 webhook
飞书多维表格状态回写
新分支通知卡片
前端高级筛选
```

这样可以最快验证核心价值，同时避免初期复杂度过高。

## 16. 最终验收标准

- 在飞书云文档中新增 GitHub/Gitee 仓库链接后，系统能自动发现仓库。
- 系统能自动识别仓库默认分支。
- 系统能自动拉取该仓库所有远端分支。
- 每个分支都能自动生成独立监控任务。
- 新建远端分支后，系统能自动补建监控任务。
- 同一个仓库不会重复创建。
- 不同 owner 下的同名仓库不会混淆。
- 分支名包含 `/` 时不会造成 job_id 冲突。
- 删除远端分支后，本地能标记为 deleted 或 paused。
- Web 页面能按仓库分组展示主分支和其他分支。
- CLI 和 Web 都能手动触发同步。
- daemon 能自动周期执行同步和分支发现。
