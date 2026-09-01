# OpenInterview 常用命令
# 用法: make <target>

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
CD_APP := cd app

.PHONY: help install install-dev lint format test test-fast run run-workers docker-up docker-down clean

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## 安装生产依赖
	$(CD_APP) && $(PIP) install -r requirements.txt

install-dev: ## 安装开发依赖（含 lint 工具）
	$(CD_APP) && $(PIP) install -r requirements.txt ruff pre-commit

lint: ## 代码静态检查
	$(CD_APP) && $(PYTHON) -m ruff check .

format: ## 代码格式化（自动修复）
	$(CD_APP) && $(PYTHON) -m ruff check --fix .

test: ## 运行完整测试套件
	$(CD_APP) && ADMIN_PASSWORD=test-admin-pw $(PYTHON) -m pytest tests/ -v

test-fast: ## 运行测试（静默模式）
	$(CD_APP) && ADMIN_PASSWORD=test-admin-pw $(PYTHON) -m pytest tests/

run: ## 启动 Web 服务
	$(CD_APP) && $(PYTHON) server.py

run-workers: ## 启动两个定时 worker（两个后台进程）
	$(CD_APP) && $(PYTHON) tasks/question_worker.py & $(PYTHON) tasks/report_worker.py &

init-db: ## 初始化数据库
	$(CD_APP) && $(PYTHON) cli.py init-db

docker-up: ## Docker Compose 启动
	docker compose up --build -d

docker-down: ## Docker Compose 停止
	docker compose down

clean: ## 清理缓存文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
