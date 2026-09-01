#!/bin/sh
# OpenInterview 容器启动脚本：同时拉起 Web 服务与两个定时 worker
echo "[start] initializing database..."
python -c "from database import init_db; init_db()"

echo "[start] launching web server and workers..."
python server.py &
python tasks/question_worker.py &
python tasks/report_worker.py &
wait
