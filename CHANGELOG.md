# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [3.0.0] - 2026-09-02

### Added 新增
- **提示词版本化注册表**：全部 LLM 提示词外置至 `app/prompts.yaml`，带唯一 ID + 语义化版本（question_generation@2.1.0 / report_evaluation@2.1.0）；`prompt_registry` 模块提供加载、变量渲染（缺变量即抛 `KeyError` 提前暴露）与清单查询；`make prompts` / `python cli.py list-prompts` 可查看当前生效版本
- **结构化日志体系**：`logging_config` 模块提供 JSON 结构化输出（生产）与人类可读控制台输出（开发）双格式，由 `LOG_FORMAT` 环境变量切换；WSGI 层 `RequestIDMiddleware` 为每个请求分配 `X-Request-ID`（响应头透出、日志全链路贯穿）；访问日志统一记录方法/路径/状态码/耗时
- **SVG 雷达图引擎**：纯 Python 生成五维能力雷达图（零 matplotlib 依赖），嵌入 PDF 评估报告；对非法分数自动钳制 0-100，脏数据不崩溃
- **Webhook 事件系统**：面试完成、问题生成、报告生成三类事件，HMAC-SHA256 签名（`X-Webhook-Signature`，GitHub Webhook 惯例格式），尽力而为语义不影响主流程；配套 `verify_signature()` 供订阅方校验
- **CLI 管理工具**（`app/cli.py`）：`init-db` / `create-admin` / `stats` / `list-prompts` / `export-report` / `cleanup` 六个子命令，覆盖初始化、运维与数据导出场景
- **工程化工具链**：`pyproject.toml`（ruff，line-length 100，启用 E/W/F/I/B/UP/SIM 规则组）、`Makefile`（install/lint/fmt/test/run/prompts/clean 快捷命令）、`.pre-commit-config.yaml`（ruff + detect-secrets）、`.editorconfig`、`.gitattributes`（LF 规范化 + 二进制标注）
- **CI/CD 流水线升级**：lint job（ruff 全仓零容忍）+ 测试矩阵（Python 3.10/3.11/3.12）双阶段；新增 Release 工作流——打 `v*` tag 自动创建 GitHub Release 并从 CHANGELOG 提取发布说明
- **社区文件**：`CONTRIBUTING.md`（开发流程/规范/PR 要求）、`CODE_OF_CONDUCT.md`、`SECURITY.md`（漏洞披露流程）、`ROADMAP.md`（版本规划）、`docs/api.md`（全接口文档）、`docs/architecture.md`（含 5 条 ADR）、`docs/deployment.md`（生产部署指南）、Issue/PR 模板
- **Dependabot**：pip 依赖每周自动检查更新
- **测试扩充至 58 个用例**：新增服务层测试（分数钳制、雷达图 SVG 健壮性、简历解析降级、提示词注册表完整性）

### Changed 变更
- **README 全面重塑**：徽章、架构图、快速开始、特性表、FAQ、英文版摘要，达到开源项目标准门面水准
- PDF 库由已废弃的 PyPDF2 迁移至继任者 pypdf（消除 DeprecationWarning）
- 题目生成与报告生成服务接入提示词注册表（原硬编码字符串），便于 A/B 与灰度迭代
- `generate_interview_questions.py` / `generate_interview_reports.py` 两个 v0 独立脚本同步 lint 修复，全仓 ruff 零告警

### Security 安全
- `.env.example` 补充 `LOG_FORMAT` / `WEBHOOK_URL` / `WEBHOOK_SECRET` 配置说明
- 敏感文件扫描确认：`.env`、证书（`.key`/`.pem`）、数据库（`.db`）均未入库

## [2.0.0] - 2026-09-02

### Added 新增
- **管理端登录系统**：PBKDF2-HMAC-SHA256 口令哈希 + HMAC 签名会话令牌（12 小时有效期），独立登录页，首次启动自动生成随机口令并打印至日志（或由 `ADMIN_PASSWORD` 环境变量指定）
- **接口权限矩阵**：管理端全部写接口（岗位/候选人/面试 CRUD、报告下载、看板）统一 `@admin_required` 保护；伪造/过期令牌一律 401
- **接口限流**：登录（5 次/分钟/IP）、简历投递（30 次/小时/IP）、答案提交（6 次/分钟/面试）
- **数据看板**：岗位/候选人/面试总数、各状态分布、近 7 天面试量柱状图（`GET /api/stats/dashboard`）
- **安全响应头**：`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` / `Permissions-Policy`
- **健康检查**：`GET /api/health` 返回版本号
- **结构化出题**：每题带能力维度（技术深度/项目复盘/系统设计/行为素质）、难度（easy/medium/hard）、题型与追问建议；难度递进（前 1/3 基础 → 后 1/3 挑战）
- **深度评估报告 v2**：分维度得分、核心优势、主要短板、下一轮追问方向、录用建议与理由；PDF 报告全新排版（分维度表格、逐题追问框）
- **pytest 测试套件**：44 个用例（安全模块单元测试、API 集成测试、权限矩阵参数化、业务流测试），CI 中 mock 重依赖可跑
- **面试页体验**：录音波形动画、题目维度/难度徽章、录音过短防误触确认、未到面试时间提示、暗色模式适配
- **管理端体验**：暗色模式切换、SweetAlert2 Toast 替换原生弹窗、删除二次确认（说明级联影响）、退出登录、口令修改页
- **数据库加固**：WAL 模式、外键约束、5 个常用索引、settings 键值表、v1→v2 自动列迁移
- **LLM 调用加固**：指数退避重试（3 次）、120 秒超时、超长简历截断（8000 字符）

### Changed 变更
- 删除岗位/候选人时级联清理关联面试与问题记录（原来仅删面试自身）
- 提交答案接口先释放数据库连接再执行耗时转写，降低连接占用
- 前端统一鉴权 fetch 封装：自动携带令牌、401 自动跳转登录页
- CI 升级为运行真实 pytest 套件（原为内联冒烟脚本）

### Security 安全
- 管理端接口此前完全匿名可访问，现全部要求会话鉴权
- 登录口令以 PBKDF2（260,000 迭代）存储，不存明文；签名比较使用 `hmac.compare_digest` 防时序攻击

## [1.0.0] - 2026-09-02

### Added 新增
- 首个开源版本：Flask 模块化后端（api/services/tasks 分层）
- LLM 面试问题生成与 PDF 评估报告
- Whisper 语音面试（录音上传 → 转录 → 存库）
- Vue3 + Bootstrap 管理后台与候选人面试页
- Docker Compose 部署、MIT License
- 安全基线：无密钥/证书/个人信息入库，`.env.example` 模板
