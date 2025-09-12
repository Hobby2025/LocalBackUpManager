// 백업 상세 페이지 스크립트 (CRLF)
(function () {
  "use strict";

  const backupId = window.__BACKUP_ID__;
  const elId = document.getElementById("bk-id");
  const elStatus = document.getElementById("bk-status");
  const elType = document.getElementById("bk-type");
  const elRatio = document.getElementById("bk-ratio");
  const elSize = document.getElementById("bk-size");
  const elEncrypted = document.getElementById("bk-encrypted");
  const elPath = document.getElementById("bk-path");
  const elChecksum = document.getElementById("bk-checksum");
  const elDuration = document.getElementById("bk-duration");
  const elCompleted = document.getElementById("bk-completed");
  const elError = document.getElementById("bk-error");

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

  async function loadDetail() {
    try {
      const res = await fetch(`/api/backups/${encodeURIComponent(backupId)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "백업 상세 조회 실패");

      elId.textContent = data.id || backupId;
      elStatus.textContent = data.status || "-";
      elType.textContent = data.backup_type || "-";
      elRatio.textContent =
        typeof data.compression_ratio === "number"
          ? `${data.compression_ratio}%`
          : "-";
      const sizeValue =
        data.compressed_size != null ? data.compressed_size : data.file_size;
      elSize.textContent = humanSize(sizeValue);
      elEncrypted.textContent = data.is_encrypted ? "예" : "아니오";
      elPath.textContent = data.file_path || "-";
      elChecksum.textContent = data.checksum || "-";
      elDuration.textContent =
        data.duration_seconds != null ? String(data.duration_seconds) : "-";
      elCompleted.textContent = data.completed_at
        ? new Date(data.completed_at).toLocaleString()
        : "-";

      // 오류 메시지 표시
      if (data.error_message) {
        elError.classList.remove("d-none");
        elError.textContent = data.error_message;
      } else {
        elError.classList.add("d-none");
      }
    } catch (e) {
      console.error(e);
      elError.classList.remove("d-none");
      elError.textContent = e.message || "백업 상세 조회 실패";
    }
  }

  document.addEventListener("DOMContentLoaded", loadDetail);
})();
