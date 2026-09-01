# OpenInterview 架构设计

本文面向希望理解内部机制、参与贡献或进行二次开发的开发者。

## 目录

- [总览](#总览)
- [分层架构](#分层架构)
- [核心设计决策（ADR 摘要）](#核心设计决策adr-摘要)
- [数据模型](#数据模型)
- [请求生命周期](#请求生命周期)
- [定时任务模型](#定时任务模型)
- [LLM 集成层](#llm-集成层)
- [安全模型](#安全模型)
- [性能与容量](#性能与容量)
- [扩展指南](#扩展指南)

---

## 总览

```
┌────────────────────────────────────────────────────────────┐
│                      浏览器（Vue3 CDN）                       │
│   admin.html 管理控制台     interview.html 候选人面试页        │
└─────────────┬──────────────────────────┬───────────────────┘
              │ Bearer 会话               │ token 凭据
┌─────────────▼──────────────────────────▼───────────────────┐
│                Flask 应用（server.py 应用工厂）               │
│  RequestID 中间件 → CORS → 安全响应头 → 蓝图路由              │
│  ┌─────────┐ ┌────────────┐ ┌──────────────────────────┐   │
│  │ api/    │ │ security.py│ │ logging_config.py        │   │
│  │ 蓝图层   │ │ 鉴权/限流   │ │ request-id / JSON 日志    │   │
│  └────┬────┘ └────────────┘ └──────────────────────────┘   │
│       ▼                                                     │
│  ┌──────────────────── services/ ────────────────────────┐  │
│  │ llm.py(重试/退避)  asr.py(Whisper)  resume.py(PDF解析)  │  │
│  │ question_service.py  report_service.py  radar.py       │  │
│  │ webhook.py(HMAC 签名事件)                               │  │
│  └────┬─────────────────────────────────────────────────┬─┘  │
│       ▼                                                 ▼    │
│  prompt_registry.py(prompts.yaml)            database.py     │
└─────────────────────────────────────────────┬───────────────┘
                                              ▼
                              SQLite（WAL）+ 定时 worker ×2
```

## 分层架构

| 层 | 目录 | 职责 | 依赖方向 |
|----|------|------|----------|
| 入口 | `server.py` | 应用工厂、中间件注册 | → 所有层 |
| 路由 | `api/` | 参数校验、鉴权、HTTP 语义 | → services, security, database |
| 服务 | `services/` | 业务逻辑（LLM/ASR/报告/雷达/Webhook） | → llm, database, prompt_registry |
| 基础 | `database.py` `security.py` `logging_config.py` `config.py` | 横切关注点 | 无内部依赖 |
| 任务 | `tasks/` | 周期调度的 worker 进程 | → services |
| 配置 | `config.py` `prompts.yaml` | 环境变量注入 / 提示词版本化 | 无 |

**规则**：`api/` 不写业务逻辑；`services/` 不感知 HTTP（不 import flask）；跨层只允许向下依赖。

## 核心设计决策（ADR 摘要）

### ADR-001：选择 SQLite 而非 PostgreSQL

- **背景**：目标用户是中小团队，希望「克隆即跑」。
- **决策**：默认 SQLite（WAL 模式），部署零依赖；连接短平快（每操作开/关），避免锁竞争。
- **后果**：单机写入吞吐有限（WAL 下读并发良好）；如需水平扩展，`database.py` 是唯一需要替换的模块（接口已收窄为 `get_db()`）。

### ADR-002：报告以 BLOB 存库而非文件系统

- **决策**：PDF 直接存 `interviews.report_content` BLOB。
- **理由**：备份语义简单（单文件备份即全量）；下载接口零路径拼接，天然避免路径穿越。
- **代价**：数据库体积随报告增长；`cli.py cleanup` 提供 N 天前录音清理与 VACUUM 提示缓解。

### ADR-003：管理端鉴权采用无状态 HMAC 令牌而非 session 表

- **决策**：`expiry.nonce.signature` 三段式令牌，HMAC-SHA256 签名。
- **理由**：无需会话表与过期清理；重启服务不失效（密钥持久化在实例目录）。
- **代价**：无法服务端主动吊销单个会话（logout 是客户端语义）。如需吊销能力，在 `settings` 表加黑名单即可，接口已预留。

### ADR-004：提示词外置 YAML 并版本化

- **决策**：`prompts.yaml` 集中管理，`prompt_registry.py` 提供渲染与版本查询；修改提示词只需改 YAML + 递增 version。
- **理由**：提示词是本项目的核心资产之一，迭代频率远高于代码；独立版本化让效果回归与 A/B 对比可追溯。

### ADR-005：出题/报告 worker 采用轮询而非消息队列

- **决策**：`schedule` 每 N 分钟轮询状态字段。
- **理由**：状态机天然存于 `interviews.status`，轮询实现最简单、可观测（看板直接读状态分布）、崩溃恢复零成本（重启接着扫）。
- **边界**：事件延迟 ≤ 轮询间隔（默认 5 分钟）。若需秒级时效，对接 Webhook 消费方即可，无需改内核。

## 数据模型

```
positions 1 ─── n candidates 1 ─── n interviews 1 ─── n interview_questions
                                     │
                                     ├── report_content (PDF BLOB)
                                     └── token (候选人端凭据，建了索引)
```

- `interview_questions.v2 新列`：`question_type` / `difficulty` / `dimension` —— 结构化出题的落点，启动时自动迁移旧库
- `settings`：键值表，当前存管理员口令哈希；是轻量「系统配置」扩展点
- 索引：`token`（候选人端高频查）、`status`（worker 轮询）、`candidate_id`、`interview_id`、`position_id`

## 请求生命周期

```
HTTP 请求
  → RequestIDMiddleware        透传/生成 X-Request-ID
  → Flask 路由匹配
  → @admin_required（管理端）   Bearer 令牌 HMAC 验签 + 过期检查
  → rate_limiter.check（敏感端点）滑动窗口计数
  → 业务处理                    api/ → services/
  → after_request               access log（含耗时）、安全响应头
  → 响应                        X-Request-ID 回传
```

未捕获异常由统一 errorhandler 兜底：JSON 500（生产）/ 抛出便于调试（DEBUG 模式），日志携带 request_id 与堆栈。

## 定时任务模型

```
question_worker.py ─┐                      ┌─ status=0 → 生成题目 → status=1 → webhook
                    ├─ schedule.every(5min) ┤
report_worker.py  ──┘                      └─ status=3 → LLM 评估 → PDF → status=4 → webhook
```

- **幂等性**：worker 只按状态字段扫描，重复执行不会产生重复数据
- **故障隔离**：单场面试失败只记日志，不影响同批其他场次
- **优雅停机**：KeyboardInterrupt 退出；因幂等，kill -9 也安全

## LLM 集成层

```
services/llm.py
  ├─ 单例 OpenAI 客户端（OPENAI_BASE_URL 可指向任意兼容服务）
  ├─ 指数退避重试 ×3（2s/4s/8s + 抖动）
  ├─ 120s 超时
  └─ _extract_json()：兼容 markdown 代码块 / 前后噪声文本的 JSON 提取
```

提示词从 `prompts.yaml` 加载（`prompt_registry.render_prompt`），服务层零硬编码提示词。

## 安全模型

| 面 | 措施 |
|----|------|
| 管理端认证 | PBKDF2（260k 迭代）口令哈希；HMAC 签名会话；`compare_digest` 防时序 |
| 暴力破解 | 登录限流 5 次/分/IP |
| 候选人端 | 32 位随机 token；提交限流；未到开始时间 403 |
| 输入 | 简历 ≤10MB；SQL 全参数化；PDF 解析失败降级不崩 |
| 传输 | 响应安全头；生产强制 HTTPS（nginx 层） |
| 隐私 | 删除级联（候选人→面试→问题含录音）；`cli.py cleanup` 定期清录音；文档明示合规责任 |

## 性能与容量

参考量级（4 核 8G，CPU Whisper base）：

- API 响应（除转写/LLM）< 50ms
- Whisper base CPU 转录 1 分钟音频 ≈ 20-40s（GPU large-v3 ≈ 2-5s）
- 报告生成受 LLM 延迟主导（10-40s），worker 异步化后不影响用户
- SQLite 在 WAL 下支撑中小团队（日均百场面试）绰绰有余

瓶颈识别：音频转写是同步阻塞点（占用 worker 线程）。规模扩大时优先项：①转写改异步任务队列 ②Whisper 换 faster-whisper（同模型 4 倍速）。

## 扩展指南

| 想做什么 | 改哪里 |
|----------|--------|
| 新增 REST 接口 | `api/` 加蓝图方法（写接口套 `@admin_required`），在 `server.py` 注册 |
| 换 LLM 供应商 | 改 `.env` 的 `OPENAI_BASE_URL`/`LLM_MODEL`，无需改代码 |
| 调整出题/评估策略 | 改 `prompts.yaml`（递增 version） |
| 新增评估维度 | `services/radar.py` 的 `DIMENSIONS` + `prompts.yaml` 的 dimension 说明 + 报告模板 |
| 更换数据库 | 重写 `database.get_db()`，保持游标语义即可 |
| 事件对接自动化 | 消费 [Webhook 事件](api.md#webhook-事件)，或扩展 `services/webhook.py` 新事件 |
