# OpenInterview 生产部署指南

从裸机到公网可用的完整路径。按顺序执行即可。

## 目录

- [部署方式选择](#部署方式选择)
- [Docker 部署（推荐）](#docker-部署推荐)
- [裸机部署](#裸机部署)
- [HTTPS 与反向代理](#https-与反向代理)
- [环境变量清单](#环境变量清单)
- [首次上线检查清单](#首次上线检查清单)
- [备份与恢复](#备份与恢复)
- [升级与回滚](#升级与回滚)
- [监控与告警](#监控与告警)
- [故障排查](#故障排查)

---

## 部署方式选择

| 方式 | 适用场景 | 复杂度 |
|------|----------|--------|
| Docker Compose | 绝大多数场景 | ★ |
| 裸机 + systemd | 无 Docker 环境 / 深度定制 | ★★ |
| 内网穿透 / 云函数 | 仅演示 | — |

## Docker 部署（推荐）

```bash
git clone https://github.com/<you>/OpenInterview.git
cd OpenInterview

# 1. 配置
cp app/.env.example app/.env
vim app/.env        # 必填 OPENAI_API_KEY / ADMIN_PASSWORD / SECRET_KEY

# 2. 启动（首次会构建镜像）
docker compose up --build -d

# 3. 验证
curl http://localhost:8000/api/health
docker compose logs -f app   # 观察初始管理员口令（若未设置 ADMIN_PASSWORD）
```

镜像内已包含 ffmpeg 与中文字体（Noto CJK），PDF 中文渲染开箱即用。

## 裸机部署

```bash
# 1. 系统依赖（Ubuntu/Debian 示例）
sudo apt install -y python3.11 python3.11-venv ffmpeg fonts-noto-cjk

# 2. 应用部署
cd /opt && git clone https://github.com/<you>/OpenInterview.git
cd OpenInterview/app
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. 配置
cp .env.example .env && vim .env
python cli.py init-db

# 4. systemd 服务（三份：web / question / report）
sudo tee /etc/systemd/system/openinterview-web.service > /dev/null << 'EOF'
[Unit]
Description=OpenInterview Web
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/OpenInterview/app
EnvironmentFile=/opt/OpenInterview/app/.env
ExecStart=/opt/OpenInterview/app/venv/bin/python server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# question/report worker 同理，替换 ExecStart 为
#   /opt/OpenInterview/app/venv/bin/python tasks/question_worker.py
#   /opt/OpenInterview/app/venv/bin/python tasks/report_worker.py
# 描述与文件名相应调整

sudo systemctl daemon-reload
sudo systemctl enable --now openinterview-web openinterview-question openinterview-report
```

## HTTPS 与反向代理

1. 证书放入 `nginx/ssl/`：`server.pem` + `server.key`（该目录已被 .gitignore 排除，不会泄露）
2. 编辑 `nginx/nginx.conf`：`server_name` 改为你的域名
3. 取消 `docker-compose.yml` 中 nginx 服务的注释，`docker compose up -d`

裸机部署可直接复用仓库内的 `nginx/nginx.conf`（`/api/` 反代到 8000，静态文件直接服务，HTTP 301 跳 HTTPS）。

也可以使用 Caddy（自动 HTTPS）：

```
interview.example.com {
    handle /api/* {
        reverse_proxy localhost:8000
    }
    handle {
        root * /opt/OpenInterview/app/static
        try_files {path} /admin.html
    }
}
```

## 环境变量清单

完整项见 `app/.env.example`。生产环境**必须**设置：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | LLM 密钥 |
| `ADMIN_PASSWORD` | 初始管理员口令（8 位以上强口令） |
| `SECRET_KEY` | 会话签名密钥（`python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成） |
| `PUBLIC_BASE_URL` | 对外域名（生成的面试链接用它拼接） |
| `FLASK_DEBUG` | **必须为 0/false**（生产禁用调试） |

推荐设置：

| 变量 | 说明 |
|------|------|
| `WEBHOOK_URL` / `WEBHOOK_SECRET` | 事件推送（对接 IM 机器人等） |
| `WHISPER_MODEL_GPU` | GPU 机型建议 `medium`（large-v3 需 ≥10G 显存） |
| `LOG_FORMAT=json` | 接入日志采集时开启 |

## 首次上线检查清单

- [ ] `curl /api/health` 返回 ok
- [ ] 用 `ADMIN_PASSWORD` 登录成功，并**立即在「设置」页修改口令**
- [ ] 创建岗位 → 添加候选人 → 安排面试 → 等 worker 出题（≤5 分钟）
- [ ] 手机/外网设备打开面试链接：能进欢迎页、能授权麦克风（HTTPS 必须）
- [ ] 完成一场测试面试：状态流转到「报告已生成」，PDF 可下载且中文正常
- [ ] Webhook（如配置）：用 `WEBHOOK_SECRET` 验签通过
- [ ] 备份定时任务已配置（见下）
- [ ] `FLASK_DEBUG=0`、日志按预期输出

## 备份与恢复

数据都在 SQLite 单文件 + WAL 附属文件中：

```bash
# 备份（WAL 安全快照方式）
sqlite3 app/interview_system.db ".backup '/backup/interview_$(date +%F).db'"

# crontab 每日 02:00 备份并保留 30 天
0 2 * * * sqlite3 /opt/OpenInterview/app/interview_system.db ".backup '/backup/interview_$(date +\%F).db'" && find /backup -name 'interview_*.db' -mtime +30 -delete
```

恢复：停服务 → 用备份文件替换 `interview_system.db` → 起服务。

合规提示：备份文件含简历与面试录音（个人信息），请加密存储并控制访问权限，遵守所在司法辖区数据保护法规（PIPL/GDPR 等）。

## 升级与回滚

```bash
git pull
docker compose up --build -d      # Docker 方式
# 或裸机: pip install -r requirements.txt && systemctl restart openinterview-*

# 回滚
git checkout v2.0.0 && docker compose up --build -d
```

数据库迁移自动执行（启动时补列，向前兼容），回滚到旧版本前建议先备份。

## 监控与告警

- **存活**：`/api/health` 接入 UptimeRobot / Prometheus blackbox
- **日志**：`LOG_FORMAT=json` 后 stdout 可被 docker logs / Loki 采集；每条日志含 `request_id`
- **业务指标**：`GET /api/stats/dashboard`（需会话）或 `python cli.py stats`
- **worker 存活**：systemd `Restart=always` 已兜底；Docker 用 `restart: unless-stopped`

## 故障排查

| 症状 | 排查 |
|------|------|
| 面试链接打不开 | `PUBLIC_BASE_URL` 是否为公网可达地址；HTTPS 下麦克风权限才可用 |
| 状态一直「未开始」 | worker 是否在跑；worker 日志有无 LLM 报错（密钥/额度） |
| 转录失败 | 容器内 ffmpeg 是否可用（`docker compose exec app ffmpeg -version`） |
| PDF 中文乱码 | 裸机部署需装 `fonts-noto-cjk` |
| 429 Too Many Requests | 触发限流，检查是否有脚本在刷接口 |
| 登录一直失败 | 首次口令看启动日志；确认不是限流窗口期（5 分钟） |
| 报告下载 404 | 状态未到 4；查 report worker 日志 |
