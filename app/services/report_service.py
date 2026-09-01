"""
OpenInterview - 面试报告生成服务（v2）

v2 增强：
- 分维度得分（technical/project/design/behavior 四维，供前端雷达图）
- 结构化评语：优势 strengths / 短板 weaknesses / 追问建议 followup_suggestions
- 评分离散化校验（0-100 整数钳制）
- 录用建议带置信度说明
"""
from datetime import datetime

from jinja2 import Environment
from weasyprint import HTML

from config import config
from constants import QUESTION_FULL_SCORE, InterviewStatus
from database import get_db
from services.llm import chat_json

VALID_DIMENSIONS = {"technical": "技术深度", "project": "项目复盘", "design": "系统设计", "behavior": "行为素质"}


def _clamp_score(value, default=None):
    """将模型输出的分数钳制为 0-100 整数；无法解析返回 default"""
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, score))


def call_ai_model(candidate_name, position_name, interviewer, questions) -> dict:
    """调用 LLM 进行深度评估，返回结构化结果（失败时返回空壳由调用方降级）"""
    prompt_parts = [
        f'你是一位资深的面试评估专家，正在评估候选人"{candidate_name}"应聘"{position_name}"职位的面试表现。'
        f"面试官是 {interviewer}。\n\n",
        "评估要求：\n"
        f"1. 每题按评分标准打分，分数为 0-{QUESTION_FULL_SCORE} 的整数；\n"
        "2. 点评必须具体到候选人的实际回答内容，引用其原话关键片段，杜绝空话；\n"
        "3. 综合评估需指出：核心优势（3条以内）、主要短板（3条以内）、若进入下一轮值得追问的方向；\n"
        "4. 录用建议从「强烈推荐 / 推荐录用 / 可以考虑 / 不建议录用」四档中选择，并简述理由。\n\n",
        "以下是面试问答记录：\n",
    ]
    for i, q in enumerate(questions, 1):
        prompt_parts.append(
            f"问题{i}（维度: {q.get('dimension') or '综合'}，题型: {q.get('question_type') or 'technical'}）:\n"
            f"题目: {q.get('question', '未提供问题')}\n"
            f"评分标准: {q.get('score_standard', '未提供评分标准')}\n"
            f"候选人回答: {q.get('answer_text') or '未作答'}\n\n"
        )

    prompt_parts.append(
        f"请以 JSON 返回，结构如下（分数均为 0-{QUESTION_FULL_SCORE} 整数）：\n"
        "{\n"
        '  "question_evaluations": [{"id": 1, "score": 85, "comments": "…引用回答关键片段的具体点评…", "followup": "针对此题的追问建议"}],\n'
        '  "dimension_scores": {"technical": 85, "project": 80, "design": 75, "behavior": 90},\n'
        f'  "technical_score": 85, "communication_score": 90, "overall_score": 84,\n'
        '  "strengths": ["优势1", "优势2"],\n'
        '  "weaknesses": ["短板1", "短板2"],\n'
        '  "followup_suggestions": ["下一轮建议追问：…", "…"],\n'
        '  "comments": "综合评语（150字以内）",\n'
        '  "recommendation": "推荐录用", "recommendation_reason": "理由"\n'
        "}\n"
        "未作答的题目 score 记 0，comments 注明「未作答」。"
    )

    try:
        result = chat_json(
            "你是一位专业的面试评估专家，负责技术面试的深度评估。只输出 JSON。",
            "\n".join(prompt_parts),
        )

        # 评分离散化校验
        for ev in result.get("question_evaluations", []) or []:
            ev["score"] = _clamp_score(ev.get("score"), 0)
        dim = {}
        for key, label in VALID_DIMENSIONS.items():
            raw = (result.get("dimension_scores") or {}).get(key)
            dim[key] = {"label": label, "score": _clamp_score(raw)}
        result["dimension_scores"] = dim
        for key in ("technical_score", "communication_score", "overall_score"):
            result[key] = _clamp_score(result.get(key))
        if not isinstance(result.get("strengths"), list):
            result["strengths"] = []
        if not isinstance(result.get("weaknesses"), list):
            result["weaknesses"] = []
        if not isinstance(result.get("followup_suggestions"), list):
            result["followup_suggestions"] = []
        return result
    except Exception as e:
        print(f"[report] 调用 LLM 失败: {e}")
        return {}


def generate_pdf_report(candidate_name, position_name, interviewer,
                        evaluation_result, questions_meta, answers) -> bytes:
    """渲染 v2 深度报告模板并转换为 PDF"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>面试评估报告</title>
        <style>
            body { font-family: 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif; margin: 36px; color: #222; }
            .container { max-width: 820px; margin: auto; }
            .header { text-align: center; border-bottom: 3px solid #1a5fb4; padding-bottom: 16px; }
            .header h1 { margin: 0; color: #1a5fb4; letter-spacing: 4px; }
            .meta { color: #666; font-size: 12px; margin-top: 6px; }
            .section { margin-top: 24px; }
            .section h2 { color: #1a5fb4; font-size: 16px; border-left: 4px solid #1a5fb4; padding-left: 8px; }
            .table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            .table th, .table td { border: 1px solid #d5d5d5; padding: 8px 10px; text-align: left; font-size: 13px; }
            .table th { background-color: #eef4fc; }
            .overall { display: flex; gap: 12px; }
            .overall .cell { flex: 1; border: 1px solid #d5d5d5; border-radius: 8px; padding: 14px; text-align: center; }
            .overall .num { font-size: 28px; font-weight: bold; color: #1a5fb4; }
            .overall .lbl { font-size: 12px; color: #666; margin-top: 4px; }
            .list-box { border: 1px solid #d5d5d5; border-radius: 8px; padding: 12px 16px; margin-top: 10px; }
            .list-box ul { margin: 4px 0; padding-left: 18px; }
            .list-box li { font-size: 13px; line-height: 1.7; }
            .strengths h3 { color: #26a269; font-size: 13px; margin: 6px 0; }
            .weaknesses h3 { color: #c01c28; font-size: 13px; margin: 6px 0; }
            .question-section { border: 1px solid #d5d5d5; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; page-break-inside: avoid; }
            .q-head { display: flex; justify-content: space-between; align-items: baseline; }
            .question-title { font-weight: bold; color: #333; font-size: 13px; }
            .score-badge { font-weight: bold; color: #1a5fb4; white-space: nowrap; }
            .q-body { font-size: 12px; color: #444; line-height: 1.7; margin-top: 6px; }
            .q-body .k { color: #888; }
            .followup { background: #f6f8fa; border-left: 3px solid #1a5fb4; padding: 6px 10px; margin-top: 6px; font-size: 12px; }
            .recommendation-box { border: 2px solid #1a5fb4; border-radius: 8px; padding: 14px 18px; text-align: center; }
            .recommendation-box .rec { font-size: 20px; font-weight: bold; color: #1a5fb4; }
            .recommendation-box .reason { font-size: 12px; color: #555; margin-top: 6px; }
            .footer { margin-top: 30px; text-align: center; color: #999; font-size: 11px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>面试评估报告</h1>
                <div class="meta">{{ interview_date }} · OpenInterview 智能评估</div>
            </div>

            <div class="section">
                <table class="table">
                    <tr><th style="width:18%">候选人</th><td>{{ candidate_name }}</td>
                        <th style="width:18%">应聘职位</th><td>{{ position }}</td></tr>
                    <tr><th>面试官</th><td>{{ interviewer }}</td><th>评估模型</th><td>{{ model_name }}</td></tr>
                </table>
            </div>

            <div class="section">
                <h2>综合评分</h2>
                <div class="overall">
                    <div class="cell"><div class="num">{{ technical_score ?? '—' }}</div><div class="lbl">技术能力</div></div>
                    <div class="cell"><div class="num">{{ communication_score ?? '—' }}</div><div class="lbl">沟通表达</div></div>
                    <div class="cell"><div class="num">{{ overall_score ?? '—' }}</div><div class="lbl">综合评分</div></div>
                </div>
            </div>

            <div class="section">
                <h2>分维度表现</h2>
                <table class="table">
                    <tr><th>维度</th>{% for k, v in dimension_scores.items() %}<th>{{ v.label }}</th>{% endfor %}</tr>
                    <tr><th>得分</th>{% for k, v in dimension_scores.items() %}<td>{{ v.score if v.score is not none else '—' }}</td>{% endfor %}</tr>
                </table>
            </div>

            <div class="section">
                <h2>结构化评价</h2>
                <div class="list-box strengths">
                    <h3>核心优势</h3>
                    <ul>{% for s in strengths %}<li>{{ s }}</li>{% else %}<li>（未生成）</li>{% endfor %}</ul>
                </div>
                <div class="list-box weaknesses">
                    <h3>主要短板</h3>
                    <ul>{% for w in weaknesses %}<li>{{ w }}</li>{% else %}<li>（未生成）</li>{% endfor %}</ul>
                </div>
            </div>

            <div class="section">
                <h2>面试官评语</h2>
                <div class="list-box"><p style="font-size:13px; line-height:1.8;">{{ comments }}</p></div>
            </div>

            <div class="section">
                <h2>录用建议</h2>
                <div class="recommendation-box">
                    <div class="rec">{{ recommendation or '—' }}</div>
                    <div class="reason">{{ recommendation_reason or '' }}</div>
                </div>
            </div>

            <div class="section">
                <h2>逐题评估详情</h2>
                {% for q in question_evaluations %}
                <div class="question-section">
                    <div class="q-head">
                        <span class="question-title">问题{{ loop.index }} · {{ questions[loop.index0].dimension if questions|length >= loop.index else '' }}</span>
                        <span class="score-badge">{{ q.score }} / 100</span>
                    </div>
                    <div class="q-body">
                        <p><span class="k">题目：</span>{{ questions[loop.index0].question if questions|length >= loop.index else '' }}</p>
                        <p><span class="k">回答：</span>{{ answers[loop.index0] if answers|length >= loop.index else '' }}</p>
                        <p><span class="k">点评：</span>{{ q.comments }}</p>
                        {% if q.followup %}<div class="followup">追问建议：{{ q.followup }}</div>{% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>

            <div class="section">
                <h2>下一轮追问方向</h2>
                <div class="list-box">
                    <ul>{% for f in followup_suggestions %}<li>{{ f }}</li>{% else %}<li>（未生成）</li>{% endfor %}</ul>
                </div>
            </div>

            <div class="footer">Generated by OpenInterview · AI 评估结果仅供参考，最终录用决策请结合人工判断</div>
        </div>
    </body>
    </html>
    """

    # 对齐逐题渲染数据
    questions_meta_render = [
        {"question": q.get("question", ""), "dimension": q.get("dimension") or "综合"}
        for q in questions_meta
    ]

    render_data = {
        "interview_date": datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        "candidate_name": candidate_name,
        "position": position_name,
        "interviewer": interviewer,
        "model_name": config.LLM_MODEL,
        "technical_score": evaluation_result.get("technical_score"),
        "communication_score": evaluation_result.get("communication_score"),
        "overall_score": evaluation_result.get("overall_score"),
        "dimension_scores": evaluation_result.get("dimension_scores", {}),
        "strengths": evaluation_result.get("strengths", []),
        "weaknesses": evaluation_result.get("weaknesses", []),
        "comments": evaluation_result.get("comments") or "评估生成失败，请人工复核",
        "recommendation": evaluation_result.get("recommendation"),
        "recommendation_reason": evaluation_result.get("recommendation_reason"),
        "followup_suggestions": evaluation_result.get("followup_suggestions", []),
        "question_evaluations": evaluation_result.get("question_evaluations", []),
        "questions": questions_meta_render,
        "answers": answers,
    }

    env = Environment()
    template = env.from_string(html_template)
    rendered = template.render(**render_data)
    return HTML(string=rendered).write_pdf()


def update_interview_report(interview_id: int, report_content: bytes) -> None:
    """保存报告并更新状态为「报告已生成」"""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE interviews SET report_content = ?, status = ? WHERE id = ?",
            (report_content, int(InterviewStatus.REPORT_GENERATED), interview_id),
        )
        conn.commit()
    finally:
        conn.close()


def process_pending_reports() -> None:
    """扫描所有「面试完毕」的面试，逐一生成深度报告（单场失败不影响其他场次）"""
    print(f"[report] [{datetime.now():%Y-%m-%d %H:%M:%S}] 检查需要生成报告的面试...")

    conn = get_db(row_factory=True)
    interviews = [dict(r) for r in conn.execute(
        "SELECT id, candidate_id, interviewer FROM interviews WHERE status = ?",
        (int(InterviewStatus.COMPLETED),),
    ).fetchall()]
    conn.close()

    if not interviews:
        print("[report] 暂无需要生成报告的面试")
        return

    print(f"[report] 找到 {len(interviews)} 场待评估面试")

    for interview in interviews:
        interview_id = interview["id"]
        try:
            conn = get_db(row_factory=True)
            candidate = conn.execute(
                "SELECT id, name, position_id FROM candidates WHERE id = ?",
                (interview["candidate_id"],),
            ).fetchone()
            conn.close()
            if not candidate:
                print(f"[report] 找不到候选人 {interview['candidate_id']}，跳过")
                continue

            conn = get_db(row_factory=True)
            position = conn.execute(
                "SELECT id, name FROM positions WHERE id = ?",
                (candidate["position_id"],),
            ).fetchone()
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM interview_questions WHERE interview_id = ?", (interview_id,)
            ).fetchall()]
            conn.close()
            if not position:
                print(f"[report] 找不到岗位 {candidate['position_id']}，跳过")
                continue

            evaluation = call_ai_model(
                candidate["name"], position["name"], interview["interviewer"], rows
            )
            answers = [(q.get("answer_text") or "未作答")[:500] for q in rows]

            pdf_report = generate_pdf_report(
                candidate["name"], position["name"], interview["interviewer"],
                evaluation, rows, answers
            )
            update_interview_report(interview_id, pdf_report)
            print(f"[report] 面试 {interview_id}（{candidate['name']}）深度报告已生成")
        except Exception as e:
            print(f"[report] 处理面试 {interview_id} 失败: {e}")
