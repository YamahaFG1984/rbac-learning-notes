# `seed_demo --flush` 会留下被污染的权限缓存

| 项 | 值 |
| --- | --- |
| 发现于 | `vue-v0.9.0`（实施 Vue 阶段时） |
| 影响范围 | **不是 Vue 阶段引入的**——后端已有问题，React 阶段的 `e2e/reseed.ts` 调的是同一个命令 |
| 是否已修 | ❌ **未修**（超出本阶段 `VAC-5` 的后端改动范围，留给项目主人决定） |
| 绕过办法 | 重置数据时一并 `cache.clear()` |

---

## 症状

跑完一轮 E2E / 验证脚本之后，用 `cs_manager` 登录：

```
菜单：空（显示「你还没有任何菜单权限」）
perms：['ticket:ticket:assign', 'ticket:ticket:delete', 'ticket:ticket:export']
       ← 只有他**自己**的 3 个，从 cs_specialist **继承**来的 3 个不见了
```

而数据库里一切正常：

```
role cs_manager    inherits_from=cs_specialist  直接绑定=3
role cs_specialist inherits_from=—              直接绑定=3
cs_specialist 绑定：view / create / update
cs_manager    绑定：delete / assign / export
```

直接调内核也正常：

```python
_resolve_perm_codes(u) → 6 个，全对
```

**数据对、内核对，但服务端发出去的是错的。**

---

## 机制

三件事凑在一起：

| # | 事实 |
| --- | --- |
| 1 | 权限缓存的 key 是 `rbac:perms:{user_id}:{version}`（`apps/rbac/cache.py`） |
| 2 | `manage.py flush` 会**重置 SQLite 的自增序列**，新用户拿到和上一代**相同的 ID** |
| 3 | `rbac:version` 存在 **FileBasedCache** 里，**不受数据库 flush 影响**；而 `seed_demo` **既不清缓存也不 bump 版本号** |

于是：

```
第一代种子：user id=3 是 cs_manager，缓存写入 rbac:perms:3:1
     ↓ seed_demo --flush（DB 清空重建，缓存原封不动）
第二代种子：user id=3 又是 cs_manager
     ↓ 服务端读缓存 → 命中 rbac:perms:3:1 → **上一代的权限**
```

**只要两代种子的内容一样，这个 bug 就是隐形的**——命中的旧值恰好是对的。
它只在两代内容不同时暴露：比如某一次种子跑了一半、或者中途改过数据。

---

## ⚠️ 排查时我自己踩的一脚（内核的注释早就写了）

第一反应是「清了缓存再查」：

```python
u = User.objects.get(username='cs_manager')
print(services.get_user_perm_codes(u))   # 3 个
cache.clear()
print(services.get_user_perm_codes(u))   # **还是 3 个** → 于是我判断「不是缓存问题」
```

**这个判断是错的。** `services.py` 里那段注释精确地预言了它：

> ⚠️ L1 必须带版本校验。`bump_version()` 只让 L2 的 key 不可达，
> **动不了已经挂在 user 对象上的属性**。同一个请求里先改权限再读权限
> （或**测试里复用同一个 user 对象**）就会读到过期值。

我复用了同一个 `u` 对象，第二次调用命中的是挂在对象上的 **L1 缓存**，
`cache.clear()` 根本碰不到它。

> 📌 **一条写在代码里、我读过、还引用过的警告，我仍然在排查时撞了上去。**
> 它值得记下来的原因不是「注释没写清楚」，而是：
> **排查时最先做的那个「快速验证」，本身也可能是错的。**

---

## 绕过办法

重置数据时一并清缓存：

```bash
python manage.py seed_demo --flush --noinput
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev')
django.setup()
from django.core.cache import cache; cache.clear()
"
```

⚠️ 还要**重启 runserver**——L1 缓存挂在 user 对象上，
但每个请求都会重新取 user，所以实际上重启不是必需的；
真正必须的是 L2（进程外缓存）被清掉。

---

## 该不该修？

**该修**，而且修法很小：`seed_demo` 在 `--flush` 之后调一次
`bump_version()` 或 `cache.clear()`。

**但本阶段没有修**，理由是 `VAC-5`：

```bash
git diff fe-v1.0.0 HEAD -- apps/ config/    # 期望：只有两个管理命令
```

Vue 阶段对后端的改动被刻意限制在「导出命令加 `--out`」这一件事上。
动 `seed_demo` 会让这条验收失效，而它**不是 Vue 阶段引入的问题**——
React 阶段的 `frontend/e2e/reseed.ts` 调的是同一个命令，有同样的暴露。

📌 **留给项目主人决定**：它属于后端 tooling 的修补，
更适合在主干上单独开一个 tag 做，顺带给 `tests/` 加一条回归。

> 为什么 React 阶段的 92 个 E2E 没红：种子是确定性的，
> 两代内容完全一样，**命中的旧缓存恰好是对的**。
> 这正是这类 bug 最讨厌的地方——它平时完全隐形。
