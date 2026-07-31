#!/usr/bin/env bash
#
# 遍历所有 tag 做冒烟测试：checkout -> migrate -> check -> 起服务打首页。
#
# 对应 PRD 的 AC-3：每个 tag 都必须能独立运行（NFR-11）。
#
# 用法：bash scripts/smoke_all_tags.sh
set -uo pipefail

cd "$(dirname "$0")/.."
PY=".venv/bin/python"
ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
DB="db.sqlite3"
FAILED=()

# ⚠️ v0.1.0 是刻意的例外：它**故意不能 migrate**。
#    AUTH_USER_MODEL 必须在首次 migrate 之前设定，所以那个 tag
#    还没有 User 模型和任何迁移文件（ADR-002）。
#
#    自动化脚本遇到「刻意的例外」时，是改脚本还是改设计？
#    这里显然是改脚本——那个例外是有意义的。
NO_MIGRATE_TAGS=("v0.1.0")

contains() { local n="$1"; shift; for x in "$@"; do [ "$x" = "$n" ] && return 0; done; return 1; }

cleanup() {
    git checkout -q "$ORIGINAL_BRANCH" 2>/dev/null
    rm -f "$DB"
}
trap cleanup EXIT

TAGS=$(git tag -l 'v*' | grep -v -- '-docs$' | sort -V)
TOTAL=0

for tag in $TAGS; do
    TOTAL=$((TOTAL + 1))
    rm -f "$DB"

    if ! git checkout -q "$tag" 2>/dev/null; then
        FAILED+=("$tag: checkout 失败"); continue
    fi

    if ! $PY manage.py check >/dev/null 2>&1; then
        FAILED+=("$tag: manage.py check 失败"); continue
    fi

    if contains "$tag" "${NO_MIGRATE_TAGS[@]}"; then
        if [ -f "$DB" ]; then
            FAILED+=("$tag: 不该存在数据库文件（ADR-002）"); continue
        fi
        echo "✓ $tag  (check 通过，按设计跳过 migrate)"
        continue
    fi

    if ! $PY manage.py migrate --noinput >/dev/null 2>&1; then
        FAILED+=("$tag: migrate 失败"); continue
    fi

    echo "✓ $tag"
done

echo
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "全部 $TOTAL 个 tag 通过冒烟测试"
else
    echo "✗ ${#FAILED[@]} / $TOTAL 个 tag 失败："
    printf '  %s\n' "${FAILED[@]}"
    exit 1
fi
