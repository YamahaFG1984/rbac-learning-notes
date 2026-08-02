#!/usr/bin/env bash
#
# 一键跑 E2E：重置数据 → 起后端 → 构建并起前端 → 跑 Playwright。
#
# ⚠️ E2E 跑的是 **vite preview（生产构建）** 而不是 dev server。
#    两个理由：
#      1. dev server 每个请求都要现场转译模块，在小内存机器上会把
#         整个套件拖垮 —— 表现是随机超时、每次红的用例都不一样，
#         极容易被误判成「E2E 就是不稳定」而加 retry 盖过去。
#      2. 测的就是用户实际拿到的那份代码。
#
# ⚠️ 用 `--mode e2e` 构建：它把权限 store 挂到 window 上，
#    供 bypass.spec.ts 的「篡改权限」测试使用。生产构建不挂。
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> 重置演示数据"
.venv/bin/python manage.py seed_demo --flush --noinput

echo "==> 启动 Django"
.venv/bin/python manage.py runserver 8000 --noreload >/tmp/rbac-e2e-django.log 2>&1 &
DJANGO_PID=$!

echo "==> 构建前端（e2e 模式）并启动 preview"
cd frontend
npm run build:e2e
npx vite preview --port 5173 >/tmp/rbac-e2e-vite.log 2>&1 &
VITE_PID=$!

cleanup() {
  kill "$DJANGO_PID" "$VITE_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> 等待服务就绪"
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:5173/api/v1/health/ >/dev/null; then break; fi
  sleep 1
done

echo "==> 跑 Playwright"
npx playwright test "$@"
