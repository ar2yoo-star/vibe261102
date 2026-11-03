(() => {
  const root = document.documentElement;
  const EMAIL = "ar2yoo@infiniq.co.kr";
  const CATEGORY_LABEL = { python: "Py", html5: "</>", ios: "iOS" };
  const LINK_LABEL = { github: "GitHub", demo: "Demo", appstore: "App Store" };

  // Theme
  const themeQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function getStoredTheme() {
    try {
      return localStorage.getItem("theme");
    } catch {
      return null;
    }
  }

  function applyTheme(theme) {
    if (theme) root.dataset.theme = theme;
    const active = theme || (themeQuery.matches ? "dark" : "light");
    root.dataset.themeActive = active;
  }

  applyTheme(getStoredTheme());
  themeQuery.addEventListener("change", () => applyTheme(getStoredTheme()));

  document.querySelector(".theme-toggle").addEventListener("click", () => {
    const next = root.dataset.themeActive === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("theme", next);
    } catch {}
    applyTheme(next);
  });

  // Mobile nav
  const navToggle = document.querySelector(".nav-toggle");
  const navMenu = document.getElementById("nav-menu");

  navToggle.addEventListener("click", () => {
    const open = navMenu.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", String(open));
    navToggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
  });

  navMenu.addEventListener("click", (e) => {
    if (e.target.closest("a")) {
      navMenu.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
    }
  });

  // Rendering
  const el = (tag, props = {}, children = []) => {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children);
    return node;
  };

  function renderProjects(projects) {
    const grid = document.getElementById("projects-grid");
    grid.replaceChildren(
      ...projects.map((p) => {
        const links = Object.entries(p.links || {})
          .filter(([, url]) => url)
          .map(([key, url]) =>
            el("a", { href: url, target: "_blank", rel: "noopener", textContent: `${LINK_LABEL[key] || key} →` })
          );

        const card = el("article", { className: "project-card reveal" }, [
          el("div", { className: "project-thumb", textContent: CATEGORY_LABEL[p.category] || "" }),
          el("div", { className: "project-body" }, [
            el("h3", { textContent: p.title }),
            el("p", { textContent: p.summary }),
            el("ul", { className: "tags" }, p.tags.map((t) => el("li", { textContent: t }))),
            el("div", { className: "project-links" }, links),
          ]),
        ]);
        card.dataset.category = p.category;
        return card;
      })
    );
  }

  function renderExperience(items) {
    const list = document.getElementById("timeline");
    list.replaceChildren(
      ...items.map((x) =>
        el("li", { className: "timeline-item reveal" }, [
          el("span", { className: "timeline-period", textContent: x.period }),
          el("h3", { textContent: x.company }),
          el("p", { className: "timeline-role", textContent: x.role }),
          el("ul", {}, x.highlights.map((h) => el("li", { textContent: h }))),
        ])
      )
    );
  }

  // Project filter
  document.querySelector(".filters").addEventListener("click", (e) => {
    const btn = e.target.closest(".filter");
    if (!btn) return;
    const filter = btn.dataset.filter;

    document.querySelectorAll(".filter").forEach((b) => {
      const active = b === btn;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-pressed", String(active));
    });

    document.querySelectorAll(".project-card").forEach((card) => {
      card.hidden = filter !== "all" && card.dataset.category !== filter;
    });
  });

  // Reveal on scroll
  const observer =
    "IntersectionObserver" in window
      ? new IntersectionObserver(
          (entries) => {
            entries.forEach((entry) => {
              if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
              }
            });
          },
          { threshold: 0.1 }
        )
      : null;

  function observeReveals() {
    document.querySelectorAll(".reveal:not(.is-visible)").forEach((node) => {
      if (observer) observer.observe(node);
      else node.classList.add("is-visible");
    });
  }

  // Copy email
  const copyBtn = document.getElementById("copy-email");
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(EMAIL);
      copyBtn.textContent = "복사됨 ✓";
    } catch {
      copyBtn.textContent = EMAIL;
    }
    setTimeout(() => (copyBtn.textContent = "주소 복사"), 2000);
  });

  document.getElementById("year").textContent = new Date().getFullYear();

  // Load data
  fetch("data/projects.json")
    .then((res) => {
      if (!res.ok) throw new Error(res.status);
      return res.json();
    })
    .then((data) => {
      renderProjects(data.projects || []);
      renderExperience(data.experience || []);
      observeReveals();
    })
    .catch(() => {
      document.getElementById("projects-grid").textContent =
        "프로젝트 데이터를 불러오지 못했습니다. 로컬 서버(예: python -m http.server)로 실행해 주세요.";
    });
})();
