// 대시보드 스크립트
// - 모니터링 API로부터 데이터를 가져와 카드/차트를 갱신
// - 10초 간격으로 자동 새로고침

(function () {
  "use strict";

  // 상태 표시 엘리먼트 참조
  const elSystemStatus = document.getElementById("system-status");
  const elSystemTimestamp = document.getElementById("system-timestamp");
  const elTotalDatabases = document.getElementById("total-databases");
  const elRecentBackups = document.getElementById("recent-backups");
  const elFailedBackups = document.getElementById("failed-backups");
  const elSuccessRate = document.getElementById("success-rate");
  const elRecentBackupsBody = document.getElementById("recent-backups-body");
  const elActiveDatabasesList = document.getElementById(
    "active-databases-list"
  );
  const elFailedLink = document.getElementById("failed-link");
  const elChartSpinner = document.getElementById("chart-spinner");
  const elThemeToggle = document.getElementById("theme-toggle");

  let backupsChart;
  let averagesChart;

  // 유틸: 텍스트 설정
  function setText(el, text) {
    if (el) el.textContent = text;
  }

  // 시스템 상태 로드
  async function loadSystemStatus() {
    try {
      const res = await fetch("/api/monitoring/status");
      if (!res.ok) throw new Error("시스템 상태 조회 실패");
      const data = await res.json();

      // 시스템 상태 뱃지 텍스트/색상 갱신
      const status = (data.system_status || "-").toLowerCase();
      setText(elSystemStatus, status);
      elSystemStatus.classList.remove(
        "text-bg-success",
        "text-bg-warning",
        "text-bg-danger",
        "text-bg-secondary"
      );
      if (status === "healthy") elSystemStatus.classList.add("text-bg-success");
      else if (status === "degraded" || status === "warning")
        elSystemStatus.classList.add("text-bg-warning");
      else if (status === "down" || status === "error")
        elSystemStatus.classList.add("text-bg-danger");
      else elSystemStatus.classList.add("text-bg-secondary");

      setText(elSystemTimestamp, data.timestamp || "-");
      setText(elTotalDatabases, data.databases?.total ?? 0);
      setText(elRecentBackups, data.backups?.recent_24h ?? 0);
      setText(elFailedBackups, data.backups?.failed ?? 0);
      setText(
        elSuccessRate,
        `성공률: ${data.backups ? data.backups.success_rate : 0}%`
      );

      // 실패 상세 링크(간단히 API 링크로 연결)
      if (elFailedLink) {
        const a = elFailedLink.querySelector("a");
        if (a) a.href = "/api/backups?status_filter=failed";
      }
    } catch (e) {
      console.error(e);
      if (window.Swal) {
        Swal.fire({
          icon: "error",
          title: "오류",
          text: e.message || "시스템 상태 조회 실패",
        });
      }
    }
  }

  // 대시보드 종합 데이터 로드 (최근 7일, 최근 백업, 활성 DB)
  async function loadDashboardData() {
    try {
      const res = await fetch("/api/monitoring/dashboard");
      if (!res.ok) throw new Error("대시보드 데이터 조회 실패");
      const data = await res.json();

      // 차트 데이터 구성
      const labels = (data.daily_statistics || []).map((d) => d.date).reverse();
      const totals = (data.daily_statistics || [])
        .map((d) => d.total_backups)
        .reverse();
      const successes = (data.daily_statistics || [])
        .map((d) => d.successful_backups)
        .reverse();
      const failed = (data.daily_statistics || [])
        .map((d) => d.failed_backups)
        .reverse();
      const avgDuration = (data.daily_statistics || [])
        .map((d) => d.avg_duration_seconds)
        .reverse();
      const avgCompression = (data.daily_statistics || [])
        .map((d) => d.avg_compression_ratio)
        .reverse();

      renderBackupsChart(labels, totals, successes, failed);
      renderAveragesChart(labels, avgDuration, avgCompression);

      // 최근 백업 목록
      if (elRecentBackupsBody) {
        if (!data.recent_backups || data.recent_backups.length === 0) {
          elRecentBackupsBody.innerHTML =
            '<tr><td colspan="3" class="text-center text-muted">데이터 없음</td></tr>';
        } else {
          elRecentBackupsBody.innerHTML = data.recent_backups
            .map((item) => {
              const dbName =
                item.database_display_name ||
                item.database_name ||
                item.database_id ||
                "-";
              const status = item.status || "-";
              const time = item.created_at
                ? new Date(item.created_at).toLocaleString()
                : "-";
              return `<tr><td>${escapeHtml(dbName)}</td><td>${escapeHtml(
                status
              )}</td><td>${escapeHtml(time)}</td></tr>`;
            })
            .join("");
        }
      }

      // 활성 데이터베이스 목록
      if (elActiveDatabasesList) {
        if (!data.active_databases || data.active_databases.length === 0) {
          elActiveDatabasesList.innerHTML =
            '<li class="list-group-item text-muted">데이터 없음</li>';
        } else {
          elActiveDatabasesList.innerHTML = data.active_databases
            .map((db) => {
              const name = db.display_name || db.name || db.id;
              const status = db.connection_status || "unknown";
              return `<li class="list-group-item d-flex justify-content-between align-items-center">${escapeHtml(
                name
              )}<span class="badge bg-${
                status === "connected"
                  ? "success"
                  : status === "error"
                  ? "danger"
                  : "secondary"
              }">${escapeHtml(status)}</span></li>`;
            })
            .join("");
        }
      }
    } catch (e) {
      console.error(e);
    }
  }

  // 차트 렌더링
  function renderBackupsChart(labels, totals, successes, failed) {
    const ctx = document.getElementById("backupsChart");
    if (!ctx) return;

    if (backupsChart) {
      backupsChart.data.labels = labels;
      backupsChart.data.datasets[0].data = totals;
      backupsChart.data.datasets[1].data = successes;
      backupsChart.data.datasets[2].data = failed;
      backupsChart.update();
      if (elChartSpinner) elChartSpinner.style.display = "none";
      return;
    }

    backupsChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "총 백업 수",
            data: totals,
            borderColor: "rgba(13,110,253,0.9)",
            backgroundColor: "rgba(13,110,253,0.2)",
            tension: 0.3,
            fill: true,
          },
          {
            label: "성공한 백업 수",
            data: successes,
            borderColor: "rgba(25,135,84,0.9)",
            backgroundColor: "rgba(25,135,84,0.2)",
            tension: 0.3,
            fill: true,
          },
          {
            label: "실패한 백업 수",
            data: failed,
            borderColor: "rgba(220,53,69,0.9)",
            backgroundColor: "rgba(220,53,69,0.15)",
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true },
        },
      },
    });
    if (elChartSpinner) elChartSpinner.style.display = "none";
  }

  // 평균 지표 차트 렌더링 (소요 시간/압축률)
  function renderAveragesChart(labels, avgDuration, avgCompression) {
    const ctx = document.getElementById("averagesChart");
    if (!ctx) return;

    if (averagesChart) {
      averagesChart.data.labels = labels;
      averagesChart.data.datasets[0].data = avgDuration;
      averagesChart.data.datasets[1].data = avgCompression;
      averagesChart.update();
      return;
    }

    averagesChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "평균 소요 시간(초)",
            data: avgDuration,
            borderColor: "rgba(255,193,7,0.9)",
            backgroundColor: "rgba(255,193,7,0.2)",
            tension: 0.3,
            fill: true,
            yAxisID: "y1",
          },
          {
            label: "평균 압축률",
            data: avgCompression,
            borderColor: "rgba(108,117,125,0.9)",
            backgroundColor: "rgba(108,117,125,0.2)",
            tension: 0.3,
            fill: true,
            yAxisID: "y2",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y1: { beginAtZero: true, position: "left" },
          y2: { beginAtZero: true, position: "right" },
        },
      },
    });
  }

  // 간단한 HTML 이스케이프
  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 초기 로드 및 주기적 갱신
  async function refreshAll() {
    await Promise.all([loadSystemStatus(), loadDashboardData()]);
  }

  document.addEventListener("DOMContentLoaded", function () {
    // 다크 테마 토글 상태 복원
    try {
      const savedTheme = localStorage.getItem("theme") || "light";
      setTheme(savedTheme);
    } catch {}

    // 토글 클릭 처리
    if (elThemeToggle) {
      elThemeToggle.addEventListener("click", () => {
        const current =
          document.documentElement.getAttribute("data-bs-theme") === "dark"
            ? "light"
            : "dark";
        setTheme(current);
        try {
          localStorage.setItem("theme", current);
        } catch {}
      });
    }

    refreshAll();
    setInterval(refreshAll, 10000); // 10초마다 새로고침
  });

  // 테마 적용 함수
  function setTheme(mode) {
    document.documentElement.setAttribute("data-bs-theme", mode);
  }
})();
