// 공통 UI 스크립트: 헤더 테마 토글 (CRLF)
(function () {
  "use strict";

  function applyTheme(mode) {
    document.documentElement.setAttribute("data-bs-theme", mode);
    try {
      localStorage.setItem("theme", mode);
    } catch {}
    // 버튼 라벨/아이콘 동기화
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      const icon = btn.querySelector("[data-icon]");
      if (icon) {
        icon.textContent = mode === "dark" ? "🌙" : "☀️";
      }
    }
  }

  function detectInitialTheme() {
    try {
      const saved = localStorage.getItem("theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch {}
    // OS 설정 선호 사용
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function init() {
    applyTheme(detectInitialTheme());
  }

  // 초기화
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // 이벤트 위임으로 테마 버튼 클릭 처리(동적으로 삽입되어도 동작)
  document.addEventListener("click", function (e) {
    const btn = e.target.closest("#theme-toggle");
    if (!btn) return;
    const current =
      document.documentElement.getAttribute("data-bs-theme") === "dark"
        ? "light"
        : "dark";
    applyTheme(current);
  });
})();
