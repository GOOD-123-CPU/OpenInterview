# 参与贡献 OpenInterview

感谢你愿意为项目出力！这份文档帮你快速跑通本地开发环境并提交合格贡献。

## 行为准则

参与本项目即表示你同意遵守 [Contributor Covenant](CODE_OF_CONDUCT.md)。请保持友善、专业、尊重。

## 开发环境搭建

```bash
# 1. 克隆
git clone https://github.com/<you>/OpenInterview.git
cd OpenInterview

# 2. 虚拟环境（Python 3.10+）
cd app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. 依赖
pip install -r requirements.txt

# 4. 环境变量
cp .env.example .env            # 本地开发填 OPENAI_API_KEY 即可跑通出题/报告
                                # 不填也能跑 API + 测试（测试不依赖真实 LLM）

# 5. 初始化数据库
python cli.py init-db

# 6. 启动开发服务
python server.py & python tasks/question_worker.py & python tasks/report_worker.py

# 7. 验证环境
pytest tests/                   # 应全绿
```

系统依赖（Whisper/WeasyPrint 需要）：见 [README 依赖提示](../README.md#方式二本地运行) 或 [docs/legacy/](legacy/)。

## 开发工作流

```bash
# 1. 从 main 拉分支，命名规范：
#    feat/xxx  fix/xxx  docs/xxx  refactor/xxx
git checkout -b feat/my-feature

# 2. 开发 + 自测
#    - 新功能必须带测试
#    - 跑 lint：ruff check .
#    - 跑测试：pytest tests/

# 3. 提交（Conventional Commits）
git commit -m "feat: support docx resume parsing"

# 4. 推送并开 PR
```

## 提交信息规范（Conventional Commits）

```
<type>(<scope>): <简短描述>

<可选的详细说明>

<可选的 BREAKING CHANGE / 关联 issue>
```

type 取值：`feat` `fix` `docs` `refactor` `test` `chore` `perf` `security`

示例：
- `feat(api): add webhook retry with backoff`
- `fix(report): clamp dimension scores to 0-100 (#42)`
- `security!: require auth for candidate resume download`

## 代码规范

- **格式**：ruff（`make format` 自动修复），行宽 100
- **架构分层**：`api/` 不写业务逻辑；`services/` 不 import flask；详见 [架构文档](architecture.md#分层架构)
- **提示词**：只改 `prompts.yaml`，改完递增 version；禁止在服务代码里硬编码提示词
- **SQL**：一律参数化，禁止 f-string 拼接
- **日志**：业务模块用 `logging_config.get_logger()`，生产日志为 JSON 格式
- **敏感信息**：任何密钥/证书/真实个人信息不得入库；`.env` 已被 ignore，新敏感配置一律走环境变量

## 测试要求

| 变更类型 | 要求 |
|----------|------|
| Bug 修复 | 必须附上能复现该 bug 的回归测试 |
| 新功能 | 核心路径有测试；涉及权限的新接口加入 `test_flows.py` 权限矩阵 |
| 提示词调整 | 递增版本号 + CHANGELOG 记录；无需测试（效果评估人工进行） |
| 文档 | 无 |

运行：`make test`（等价 `ADMIN_PASSWORD=test-admin-pw pytest tests/ -v`）。

## PR 检查清单

提 PR 前自查：

- [ ] `ruff check .` 无告警
- [ ] `pytest tests/` 全绿
- [ ] 新增配置项已同步到 `.env.example` 与文档
- [ ] 用户可见的变更已更新 `CHANGELOG.md`
- [ ] 提交信息符合 Conventional Commits
- [ ] 不含敏感信息（CI 也有 detect-secrets 兜底）

PR 描述请说明：改了什么、为什么、如何验证。有截图/UI 变更请附对比图。

## 报告 Bug

请附上：环境（OS/Python/部署方式）、复现步骤、期望 vs 实际、相关日志（**脱敏后**——注意日志中的 request_id 可以给，但音频、简历内容、密钥绝对不要贴）。

## 安全漏洞

**请勿公开发 Issue**！见 [SECURITY.md](SECURITY.md) 的私密上报流程。

## 项目结构速览

```
app/
├── api/            # REST 蓝图（HTTP 语义层）
├── services/       # 业务逻辑（LLM/ASR/报告/雷达/Webhook）
├── tasks/          # 定时 worker
├── tests/          # pytest
├── static/         # 前端（Vue3 CDN，免构建）
├── config.py       # 环境变量配置
├── database.py     # SQLite 封装与迁移
├── security.py     # 鉴权/限流
├── logging_config.py
├── prompt_registry.py + prompts.yaml   # 提示词工程
└── cli.py          # 运维命令行
```
