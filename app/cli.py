#!/usr/bin/env python
"""
OpenInterview - 管理命令行工具

用法:
    python cli.py init-db                 初始化数据库（建表/迁移/管理员）
    python cli.py create-admin            重置管理员口令（交互式或 --password）
    python cli.py stats                   输出数据统计摘要
    python cli.py list-prompts            列出提示词注册表及版本
    python cli.py export-report <id> <输出路径.pdf>
                                          导出面试报告 PDF
    python cli.py cleanup --days 90       清理指定天数前的已完成面试录音

示例:
    python cli.py init-db
    python cli.py create-admin --password "S3cure!"
    python cli.py export-report 1 ./report.pdf
"""
import argparse
import getpass
import json
import sys
import time

from config import config


def cmd_init_db(_args):
    from database import init_db

    init_db()
    print("✓ 数据库初始化完成")


def cmd_create_admin(args):
    from database import get_db
    from security import set_admin_password

    password = args.password or getpass.getpass("请输入新管理员口令（至少 8 位）: ")
    if len(password) < 8:
        sys.exit("✗ 口令至少 8 位")
    conn = get_db()
    set_admin_password(conn, password)
    conn.close()
    print("✓ 管理员口令已更新")


def cmd_stats(_args):
    from database import get_db

    conn = get_db(row_factory=True)
    stats = {
        "positions": conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0],
        "candidates": conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0],
        "interviews": conn.execute("SELECT COUNT(*) FROM interviews").fetchone()[0],
        "questions": conn.execute("SELECT COUNT(*) FROM interview_questions").fetchone()[0],
        "reports_generated": conn.execute(
            "SELECT COUNT(*) FROM interviews WHERE status = 4").fetchone()[0],
    }
    conn.close()
    print(json.dumps(stats, indent=2, ensure_ascii=False))


def cmd_list_prompts(_args):
    from prompt_registry import list_prompts

    for p in list_prompts():
        print(f"  {p['name']}@{p['version']}  {p['description']}")


def cmd_export_report(args):
    from database import get_db

    conn = get_db(row_factory=True)
    row = conn.execute(
        "SELECT report_content, status FROM interviews WHERE id = ?", (args.interview_id,)
    ).fetchone()
    conn.close()

    if not row or not row["report_content"]:
        sys.exit(f"✗ 面试 {args.interview_id} 的报告不存在或尚未生成")
    with open(args.output, "wb") as f:
        f.write(row["report_content"])
    print(f"✓ 报告已导出: {args.output} ({len(row['report_content']) / 1024:.0f} KB)")


def cmd_cleanup(args):
    """清理 N 天前已完成面试的录音 BLOB（保留文本与报告），释放数据库空间"""
    from database import get_db

    cutoff = int(time.time()) - args.days * 86400
    conn = get_db()
    cursor = conn.execute(
        """UPDATE interview_questions SET answer_audio = NULL
           WHERE answered_at IS NOT NULL AND answered_at < ?""",
        (cutoff,),
    )
    conn.commit()
    freed = cursor.rowcount
    conn.close()
    print(f"✓ 已清理 {freed} 条 {args.days} 天前的录音（文本与报告保留）")
    if config.DB_PATH:
        print("提示：可运行 VACUUM 回收磁盘空间，例如 sqlite3 " + config.DB_PATH)


def main():
    parser = argparse.ArgumentParser(
        prog="cli.py", description="OpenInterview 管理工具"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="初始化数据库").set_defaults(func=cmd_init_db)

    p_admin = sub.add_parser("create-admin", help="重置管理员口令")
    p_admin.add_argument("--password", help="直接指定口令（否则交互输入）")
    p_admin.set_defaults(func=cmd_create_admin)

    sub.add_parser("stats", help="数据统计摘要").set_defaults(func=cmd_stats)
    sub.add_parser("list-prompts", help="列出提示词版本").set_defaults(func=cmd_list_prompts)

    p_export = sub.add_parser("export-report", help="导出面试报告 PDF")
    p_export.add_argument("interview_id", type=int)
    p_export.add_argument("output")
    p_export.set_defaults(func=cmd_export_report)

    p_clean = sub.add_parser("cleanup", help="清理旧录音 BLOB")
    p_clean.add_argument("--days", type=int, default=90, help="保留最近 N 天（默认 90）")
    p_clean.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
