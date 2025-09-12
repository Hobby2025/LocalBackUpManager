// 데이터베이스 상세 페이지 스크립트 (CRLF)
(function () {
  "use strict";

  const databaseId = window.__DATABASE_ID__;
  const elName = document.getElementById("db-name");
  const elDisplay = document.getElementById("db-display");
  const elStatus = document.getElementById("db-status");
  const elEnv = document.getElementById("db-env");
  const elPriority = document.getElementById("db-priority");
  const elHost = document.getElementById("db-host");
  const elRecent = document.getElementById("db-recent-backups");

  // 파일 크기 가독화 유틸
  function humanSize(n) {
    if (n == null || isNaN(n)) return "-";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let s = Number(n);
    let i = 0;
    while (s >= 1024 && i < units.length - 1) {
      s /= 1024;
      i++;
    }
    return `${s.toFixed(2)} ${units[i]}`;
  }

  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  async function loadDatabase() {
    // 단건 DB 정보 조회
    try {
      const res = await fetch(
        `/api/databases/${encodeURIComponent(databaseId)}`
      );
      const it = await res.json();
      if (!res.ok) throw new Error(it.detail || "DB 상세 조회 실패");
      elName.textContent = it.name || "-";
      elDisplay.textContent = it.display_name || "-";
      elStatus.textContent = it.connection_status || "unknown";
      elEnv.textContent = it.environment || "-";
      elPriority.textContent = it.priority || "-";
      elHost.textContent = `${it.host || "-"}:${it.port || ""}`;
    } catch (e) {
      console.error(e);
    }
  }

  async function loadRecentBackups() {
    try {
      const res = await fetch(
        `/api/backups?database_id=${encodeURIComponent(databaseId)}&limit=10`
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "최근 백업 조회 실패");
      const items = data.backups || [];
      if (items.length === 0) {
        elRecent.innerHTML =
          '<tr><td colspan="6" class="text-center text-muted">데이터 없음</td></tr>';
        return;
      }
      elRecent.innerHTML = items
        .map((b) => {
          const ratio =
            typeof b.compression_ratio === "number"
              ? `${b.compression_ratio}%`
              : "-";
          const sizeValue =
            b.compressed_size != null ? b.compressed_size : b.file_size;
          const sizeText = humanSize(sizeValue);
          const completed = b.completed_at
            ? new Date(b.completed_at).toLocaleString()
            : "-";
          const link = `/backups/${encodeURIComponent(b.id)}`;
          return `<tr>
          <td>${escapeHtml(b.status || "-")}</td>
          <td>${escapeHtml(b.backup_type || "-")}</td>
          <td>${escapeHtml(ratio)}</td>
          <td>${escapeHtml(sizeText)}</td>
          <td>${escapeHtml(completed)}</td>
          <td><a class="btn btn-sm btn-outline-primary" href="${link}">보기</a></td>
        </tr>`;
        })
        .join("");
    } catch (e) {
      console.error(e);
      elRecent.innerHTML =
        '<tr><td colspan="6" class="text-center text-danger">최근 백업 조회 실패</td></tr>';
    }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    await loadDatabase();
    await loadRecentBackups();
  });
})();
