#!/usr/bin/env bash
#
# 遍历所有 fe-* tag 做冒烟测试：checkout -> npm ci -> typecheck -> build。
#
# 对应 FAC-3：每个 tag 都必须能独立运行。
#
# ⚠️ 和后端的 smoke_all_tags.sh 有一个关键区别：
#    后端每个 tag 都能「起服务打首页」，前端不行——
#    fe-v0.1.0 ~ fe-v0.4.0 时页面还没有登录，没有一个统一的「首页」可打。
#    所以这里的判定是 **typecheck + build 通过**：
#    它证明「这个 tag 的代码是自洽的」，但证明不了「跑起来是对的」。
#
#    诚实地降低判定标准，比编一个跑不通的判定要好。
#
# 用法：bash scripts/smoke_all_fe_tags.sh
set -uo pipefail

cd "$(dirname "$0")/.."
ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
FAILED=()

cleanup() {
    git checkout -q "$ORIGINAL_BRANCH" 2>/dev/null
    (cd frontend && npm install --silent >/dev/null 2>&1)
}
trap cleanup EXIT

TAGS=$(git tag -l 'fe-*' | grep -v -- '-docs$' | sort -V)
TOTAL=0

for tag in $TAGS; do
    TOTAL=$((TOTAL + 1))

    if ! git checkout -q "$tag" 2>/dev/null; then
        FAILED+=("$tag: checkout 失败"); continue
    fi

    if [ ! -d frontend ]; then
        FAILED+=("$tag: 没有 frontend 目录"); continue
    fi

    # ⚠️ 依赖会随 tag 变化（比如 fe-v0.15.0 才加 msw），
    #    所以每个 tag 都要重新安装。这也是这个脚本慢的原因。
    if ! (cd frontend && npm install --silent >/dev/null 2>&1); then
        FAILED+=("$tag: npm install 失败"); continue
    fi

    if ! (cd frontend && npx tsc -b --noEmit >/dev/null 2>&1); then
        FAILED+=("$tag: typecheck 失败"); continue
    fi

    if ! (cd frontend && npx vite build >/dev/null 2>&1); then
        FAILED+=("$tag: build 失败"); continue
    fi

    echo "  ✅ $tag"
done

echo ""
echo "共 $TOTAL 个 tag，失败 ${#FAILED[@]} 个"
for f in "${FAILED[@]}"; do echo "  ❌ $f"; done
[ ${#FAILED[@]} -eq 0 ]
