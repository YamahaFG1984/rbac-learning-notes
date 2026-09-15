// 文档站交互：主题切换、移动端侧栏、目录高亮、自检清单勾选记忆。
// 所有 localStorage 访问都包 try/catch：隐私模式下拿不到存储时页面照常可用。
(function () {
  var root = document.documentElement;

  function store(k, v) {
    try {
      if (v === undefined) return localStorage.getItem(k);
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
    } catch (e) { return null; }
  }

  // 主题：auto → light → dark 循环
  var themeBtn = document.getElementById("theme-btn");
  var labels = { auto: "◐ 跟随系统", light: "☀ 浅色", dark: "☾ 深色" };
  function applyTheme(t) {
    if (t === "light" || t === "dark") root.setAttribute("data-theme", t);
    else root.removeAttribute("data-theme");
    if (themeBtn) themeBtn.textContent = labels[t] || labels.auto;
  }
  var theme = store("rbac-theme") || "auto";
  applyTheme(theme);
  if (themeBtn) themeBtn.addEventListener("click", function () {
    theme = theme === "auto" ? "light" : theme === "light" ? "dark" : "auto";
    store("rbac-theme", theme === "auto" ? null : theme);
    applyTheme(theme);
  });

  // 移动端侧栏
  var menuBtn = document.getElementById("menu-btn");
  if (menuBtn) menuBtn.addEventListener("click", function () {
    document.body.classList.toggle("nav-open");
  });
  document.addEventListener("click", function (e) {
    if (!document.body.classList.contains("nav-open")) return;
    if (e.target.closest(".sidebar") || e.target.closest("#menu-btn")) return;
    document.body.classList.remove("nav-open");
  });
  var active = document.querySelector(".sidebar a.active");
  if (active && active.scrollIntoView) active.scrollIntoView({ block: "center" });

  // 目录随滚动高亮
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[decodeURIComponent(a.hash.slice(1))] = a; });
    var visible = {};
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visible[en.target.id] = en.isIntersecting; });
      var heads = document.querySelectorAll(".article h2[id], .article h3[id]");
      var current = null;
      for (var i = 0; i < heads.length; i++) {
        if (heads[i].getBoundingClientRect().top < 120) current = heads[i].id;
      }
      tocLinks.forEach(function (a) { a.classList.remove("on"); });
      if (current && byId[current]) byId[current].classList.add("on");
    }, { rootMargin: "-60px 0px -60% 0px" });
    document.querySelectorAll(".article h2[id], .article h3[id]").forEach(function (h) { obs.observe(h); });
  }

  // 自检清单：勾选状态按页面记在本机
  var page = location.pathname;
  document.querySelectorAll(".task-list-item input[type=checkbox]").forEach(function (box, i) {
    var key = "rbac-task:" + page + ":" + i;
    box.disabled = false;
    if (store(key) === "1") { box.checked = true; box.parentElement.classList.add("done"); }
    box.addEventListener("change", function () {
      store(key, box.checked ? "1" : null);
      box.parentElement.classList.toggle("done", box.checked);
    });
  });
})();
