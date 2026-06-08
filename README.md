# Daily MJM Analysis

每日美加墨世界杯情报分析服务。项目会采集赛程和新闻，执行规则分析与 LLM 总结，生成 Markdown / HTML 日报，并支持邮件、飞书、Telegram、企业微信推送。

## 项目目标

- 自动采集赛程、比分、积分榜、球队新闻、伤病和阵容情报
- 对比赛进行关注等级、爆冷风险、出线影响、近期状态和舆情分析
- 使用 LLM 生成中文 Markdown 日报
- 支持邮件、飞书、Telegram、企业微信推送
- 支持 GitHub Actions 定时运行和手动触发
- 通过 GitHub Secrets 管理敏感配置

## 目录结构

```text
.
|-- .github/
|   `-- workflows/
|       `-- daily_worldcup.yml
|-- analyzers/
|-- collectors/
|-- config/
|-- notifiers/
|-- reports/
|   |-- output/
|   `-- templates/
|-- storage/
|-- tests/
|-- main.py
|-- requirements.txt
`-- README.md
```

## 本地运行

1. 使用 Python 3.11。
2. 安装依赖：

```bash
python -m pip install -r requirements.txt
```

3. 复制环境变量模板并填写：

```bash
cp .env.example .env
```

4. 查看命令行帮助：

```bash
python main.py --help
```

## 常用模式

```bash
python main.py --mode fixtures --run-date 2026-06-07
python main.py --mode news
python main.py --mode analyze --run-date 2026-06-07
python main.py --mode report --run-date 2026-06-07
python main.py --mode send --run-date 2026-06-07
python main.py --mode daily --run-date 2026-06-07 --send
```

`--mode report` 会生成本地日报文件。  
`--mode send` 会先生成报告，再尝试推送到已配置渠道。  
`--mode daily --send` 会执行完整日流程：采集、分析、LLM 总结、报告生成和推送。  
如果某个推送渠道缺少配置，程序只会打印 warning 并跳过，不会报错退出。

## 配置说明

项目使用 YAML 文件保存非敏感配置，并从环境变量读取敏感信息。

### YAML 配置文件

- `config/report.yaml`
  控制时区、语言、报告章节开关、推送渠道开关。
- `config/sources.yaml`
  控制启用的数据源、RSS 源和各类数据对应的来源名。
- `config/teams.yaml`
  控制重点关注球队列表。

### 当前支持的配置项

- `timezone`
  默认值为 `Asia/Tokyo`
- `language`
  默认值为 `zh-CN`
- `focus_teams`
  默认关注 `Japan`、`United States`、`Mexico`、`Canada`
- `sections`
  控制 `overview`、`matches`、`standings`、`injuries`、`news`、`analysis`、`alerts` 是否输出
- `enabled_sources`
  控制 `schedule`、`standings`、`news`、`injuries`、`squad` 是否启用
- `push_channels`
  控制 `email`、`feishu`、`telegram`、`wecom` 是否启用

如果 YAML 文件缺失，或者字段未填写，系统会自动回退到默认值。

## 环境变量与 Secrets

以下敏感信息建议通过 `.env` 或 GitHub Secrets 提供：

### LLM

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

### 数据源

- `FOOTBALL_DATA_API_KEY`
- `NEWS_API_KEY`

配置了 `FOOTBALL_DATA_API_KEY` 后，赛程和积分榜会优先使用 `football-data.org` API；未配置时会自动回退到本地 `config/fixtures.sample.json`，积分榜则降级为空数据继续运行。

### 邮件推送

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`

### Telegram 推送

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 飞书推送

- `FEISHU_WEBHOOK_URL`

获取方式：

1. 打开目标飞书群。
2. 添加群机器人。
3. 选择自定义机器人或 Webhook 机器人。
4. 复制机器人提供的 Webhook URL。
5. 将该 URL 配置到 `FEISHU_WEBHOOK_URL`。

当前实现使用飞书机器人 Webhook 发送文本消息；如果未配置该 Secret，程序会自动跳过飞书推送。

### 企业微信推送

- `WECOM_WEBHOOK_URL`

### 其他

- `TIMEZONE`
- `REPORT_OUTPUT_DIR`

程序启动时会打印不包含密钥明文的配置摘要，便于确认当前启用状态。

## GitHub Actions 部署

工作流文件是 [daily_worldcup.yml](/e:/daily_mjm_analysis/.github/workflows/daily_worldcup.yml)。它支持：

- `workflow_dispatch` 手动触发
- `schedule` 定时触发
- 每天日本时间早上 8 点运行

说明：

- GitHub Actions 的 cron 使用 UTC。
- 日本时间 `08:00 JST` 等于前一天 `23:00 UTC`，所以工作流里使用的是 `0 23 * * *`。
- 工作流会执行：

```bash
python main.py --mode daily --send
```

- 运行完成后会把 `reports/output/` 上传为 artifact，方便下载日报文件。

### 配置 GitHub Secrets

在仓库页面进入 `Settings -> Secrets and variables -> Actions -> New repository secret`，按需添加：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `FOOTBALL_DATA_API_KEY`
- `NEWS_API_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`
- `FEISHU_WEBHOOK_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `WECOM_WEBHOOK_URL`

如果希望定时任务真正发送日报，相关推送渠道的 Secrets 需要完整配置；如果某个渠道未配置，程序会跳过该渠道而不会中断整条 workflow。

## 开发指南

### 开发环境

建议使用 Python 3.11，本地安装依赖：

```bash
python -m pip install -r requirements.txt
```

### 测试

运行全部测试：

```bash
pytest
```

运行一个基础 smoke check：

```bash
python main.py --mode fixtures
```

### 代码风格

项目已添加 `ruff` 配置，位于 [pyproject.toml](/e:/daily_mjm_analysis/pyproject.toml)。当前统一约定：

- 行宽 `88`
- 目标 Python 版本 `3.11`
- 基础检查包含导入排序和常见语法问题

如果你本地安装了 `ruff`，可以执行：

```bash
ruff check .
ruff format .
```

### 持续集成

测试工作流文件是 [test.yml](/e:/daily_mjm_analysis/.github/workflows/test.yml)。每次 `push` 或 `pull_request` 会自动执行：

```bash
python -m pip install -r requirements.txt
pytest
python main.py --mode fixtures
```

如果 CI 失败，优先检查：

- 新增依赖是否已写入 `requirements.txt`
- 新增测试是否依赖本地私有环境变量
- `fixtures` 模式是否仍能在无密钥环境下运行

## 当前状态

当前版本已经具备：

- 本地 sample 赛程采集
- RSS 新闻采集
- 规则比赛分析
- LLM 或本地降级摘要
- Markdown / HTML 报告生成
- 邮件、Telegram、企业微信推送接口
- 邮件、飞书、Telegram、企业微信推送接口
- 完整 daily pipeline
- GitHub Actions 定时运行与 artifact 上传

后续可以继续补真实比赛 API、积分榜采集、伤病阵容数据和更强的分析模型。
