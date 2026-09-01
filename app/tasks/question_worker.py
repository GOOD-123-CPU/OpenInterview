"""
OpenInterview - 面试问题生成定时任务 worker

启动后立即执行一次，之后按配置间隔（默认 5 分钟）周期执行。
"""
import time

import schedule

from config import config
from services.question_service import process_pending_interviews


def main():
    print(f"[worker] 面试问题生成服务启动，每 {config.SCHEDULE_INTERVAL_MINUTES} 分钟执行一次")
    process_pending_interviews()

    schedule.every(config.SCHEDULE_INTERVAL_MINUTES).minutes.do(process_pending_interviews)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[worker] 程序已停止")
