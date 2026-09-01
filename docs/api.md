# OpenInterview API 参考

所有接口均返回 JSON。错误响应统一格式：`{"error": "..."}` 或 `{"status": "error", "message": "..."}`。

- **Base URL**：`http://localhost:8000`（本地）/ 你的域名（生产）
- **鉴权**：管理端接口需 `Authorization: Bearer <token>`（通过登录接口获取，12 小时有效）
- **限流**：登录 5 次/分/IP；简历投递 30 次/时/IP；答案提交 6 次/分/面试
- **请求追踪**：所有响应携带 `X-Request-ID` 头，排查问题请附上此 id

---

## 目录

- [系统](#系统)
- [认证](#认证)
- [岗位](#岗位)
- [候选人](#候选人)
- [面试（管理端）](#面试管理端)
- [面试（候选人端）](#面试候选人端)
- [统计](#统计)
- [Webhook 事件](#webhook-事件)
- [面试状态机](#面试状态机)

---

## 系统

### `GET /api/health`

健康检查。

```json
{ "status": "ok", "version": "3.0.0" }
```

---

## 认证

### `POST /api/auth/login`

管理员登录。

| 请求体 | 类型 | 说明 |
|--------|------|------|
| `password` | string | 管理员口令 |

```json
// 200
{ "token": "<expiry>.<nonce>.<signature>", "expires_in": 43200 }
// 401 口令错误 / 429 尝试过多
```

### `GET /api/auth/me`

检查会话有效性。有效返回 `{"authenticated": true}`；无效返回 401。

### `PUT /api/auth/password` 🔒

修改口令。请求体：`{"old_password": "...", "new_password": "..."}`（新口令 ≥ 8 位）。

### `POST /api/auth/logout`

退出登录（无状态令牌，客户端丢弃即可；接口为审计预留）。

> 🔒 = 需要管理员会话

---

## 岗位

### `GET /api/positions`（公开）

返回岗位列表（面试页需要岗位信息，故只读公开）。

### `POST /api/positions` 🔒

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✓ | 岗位名称 |
| `requirements` | ✓ | 岗位要求 |
| `responsibilities` | ✓ | 岗位职责 |
| `quantity` | ✓ | 需求数量 |
| `status` | ✓ | 0 未启动 / 1 进行中 / 2 已完成 |
| `recruiter` | ✓ | 招聘负责人 |

### `PUT /api/positions/:id` 🔒 / `DELETE /api/positions/:id` 🔒

删除为**级联删除**：同时删除该岗位下所有候选人、面试、问题记录。

---

## 候选人

### `GET /api/candidates` 🔒

### `POST /api/candidates`（公开，限流）

`multipart/form-data` 提交：

| 字段 | 必填 | 说明 |
|------|------|------|
| `position_id` | ✓ | 岗位 ID |
| `name` | ✓ | 姓名 |
| `email` | | 邮箱 |
| `resume_content` | | PDF 简历文件（≤ 10MB） |

### `GET /api/candidates/:id/resume` 🔒

下载简历（`application/pdf` 附件）。

### `DELETE /api/candidates/:id` 🔒

级联删除候选人的面试与作答记录。

---

## 面试（管理端）

### `GET /api/interviews` 🔒

### `POST /api/interviews` 🔒

```json
{
  "candidate_id": 1,
  "interviewer": "张三",
  "start_time": 1700000000,        // Unix 秒；未到该时间候选人无法作答（可提前 5 分钟进入）
  "status": 0,
  "is_passed": 0
}
```

响应含自动生成的 32 位 `token`（即面试链接凭据）。

### `PUT /api/interviews/:id` 🔒

更新面试（token 会轮换，需重新分发链接）。

### `GET /api/interviews/:id/report` 🔒

下载 PDF 评估报告。报告未生成时返回 404 + `{"error": "面试报告尚未生成"}`。

### `DELETE /api/interviews/:id` 🔒

级联删除面试问题与录音。

---

## 面试（候选人端）

以下接口凭面试 `token` 访问（无会话），token 即唯一凭据，请勿泄露。

### `GET /api/interview/:token/info`

返回面试概要（岗位、候选人、状态、题量、朗读开关）。

### `GET /api/interview/:token/get_question?current_id=0`

获取下一题。`current_id=0` 取第一题。返回：

```json
{ "id": 12, "text": "…题目…", "dimension": "技术深度", "difficulty": "medium", "question_type": "technical" }
```

无更多题时返回 `{"id": 0, "text": "面试已完成"}`。未到面试开始时间返回 403。

### `POST /api/interview/:token/submit_answer`

`multipart/form-data`：`question_id` + `audio_answer`（音频文件，webm/ogg/wav/mp3 均可）。

服务端 Whisper 转录后存储，返回下一题（同上格式）。全部作答完毕时面试状态自动流转为「面试完毕」。

### `POST /api/interview/:token/toggle_voice_reading`

请求体 `{"enabled": true|false}`，切换题目语音朗读。

---

## 统计

### `GET /api/stats/dashboard` 🔒

```json
{
  "positions_total": 3,
  "candidates_total": 10,
  "interviews_total": 8,
  "interviews_by_status": [{ "status": 4, "label": "面试报告已生成", "count": 5 }],
  "daily_interviews_7d": [{ "date": "08-27", "count": 2 }]
}
```

---

## Webhook 事件

设置 `WEBHOOK_URL` 后，关键事件将以 `POST` 推送（超时 10s，失败不影响业务）。配合 `WEBHOOK_SECRET` 可验证来源：

```
X-OI-Signature: sha256=<hex(hmac_sha256(secret, timestamp + "." + body))>
```

| 事件 | 触发时机 | data 字段 |
|------|----------|-----------|
| `questions.generated` | 面试题目生成完毕 | `interview_id`, `candidate`, `position`, `question_count` |
| `interview.completed` | 候选人答完最后一题 | `interview_id` |
| `report.generated` | PDF 报告生成完毕 | `interview_id`, `candidate`, `position`, `overall_score`, `recommendation` |

负载统一结构：

```json
{ "event": "report.generated", "ts": 1700000000, "data": { ... } }
```

---

## 面试状态机

```
0 未开始 ──(出题 worker 生成题目)──▶ 1 试题已备好
   │                                    │
   │                          (候选人点击开始面试)
   ▼                                    ▼
 （status=0 时候选人看到"未开始"）     2 面试进行中 ──(答完最后一题)──▶ 3 面试完毕
                                                                        │
                                                           (报告 worker 评估渲染)
                                                                        ▼
                                                                   4 报告已生成
```
