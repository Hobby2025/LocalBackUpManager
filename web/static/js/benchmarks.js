// 벤치마크 리포트 페이지 스크립트 (CRLF)
(function () {
  "use strict";

  const elBody = document.getElementById("reports-body");
  const form = document.getElementById("upload-form");
  const input = document.getElementById("report-file");

  function humanSize(n) {
    if (n == null || isNaN(n)) return "-";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let s = Number(n),
      i = 0;
    while (s >= 1024 && i < units.length - 1) {
      s /= 1024;
      i++;
    }
    return `${s.toFixed(2)} ${units[i]}`;
  }

  async function loadList() {
    try {
      const res = await fetch("/api/backups/benchmarks");
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "리포트 목록 조회 실패");
      const items = data.reports || [];
      if (items.length === 0) {
        elBody.innerHTML =
          '<tr><td colspan="4" class="text-center text-muted">리포트 없음</td></tr>';
        return;
      }
      elBody.innerHTML = items
        .map((it) => {
          return `<tr>
          <td>${it.name}</td>
          <td>${humanSize(it.size)}</td>
          <td>${it.modified}</td>
          <td><a class="btn btn-sm btn-outline-primary" target="_blank" href="${
            it.path
          }">열기</a></td>
        </tr>`;
        })
        .join("");
    } catch (e) {
      console.error(e);
      elBody.innerHTML =
        '<tr><td colspan="4" class="text-center text-danger">리포트 목록 조회 실패</td></tr>';
    }
  }

  form &&
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      try {
        if (!input.files || input.files.length === 0) {
          alert("파일을 선택하세요. (CSV/JSON)");
          return;
        }
        const fd = new FormData();
        fd.append("file", input.files[0]);
        const res = await fetch("/api/backups/benchmarks", {
          method: "POST",
          body: fd,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "업로드 실패");
        input.value = "";
        await loadList();
      } catch (e) {
        console.error(e);
        alert(e.message || "업로드 실패");
      }
    });

  document.addEventListener("DOMContentLoaded", loadList);
})();
