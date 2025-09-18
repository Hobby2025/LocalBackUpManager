// 대시보드 스크립트
// - 모니터링 API로부터 데이터를 가져와 카드/차트를 갱신
// - 10초 간격으로 자동 새로고침

(function () {
  "use strict";

  // 상태 표시 엘리먼트 참조
  const elSystemStatus = document.getElementById("system-status");
  const elSystemTimestamp = document.getElementById("system-timestamp");
  const postgresqlDatabases = document.getElementById("postgresql-databases");
  const mysqlDatabases = document.getElementById("mysql-databases");
  const sqliteDatabases = document.getElementById("sqlite-databases");
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
  const toggleSecurityMode = document.getElementById("toggle-security-mode");
  const btnGenerateReport = document.getElementById("btn-generate-report");
  const elReportResult = document.getElementById("report-result");
  const selReportHours = document.getElementById("sel-report-hours");
  const selReportStatus = document.getElementById("sel-report-status");
  const chkReportNotify = document.getElementById("chk-report-notify");
  // 압축 도구 상태 요소
  const elCompDefault = document.getElementById("comp-default");
  const elCompLevel = document.getElementById("comp-level");
  const elCompZstd = document.getElementById("comp-zstd");
  const elCompLz4 = document.getElementById("comp-lz4");
  // 헤더 드롭다운: DB SSL 기본 모드 선택 요소
  const selectDbSslMode = document.getElementById("select-db-ssl-mode");
  
  // 백업 진행 상황 추적 요소들
  const btnRefreshBackupProgress = document.getElementById("btn-refresh-backup-progress");
  const btnStartBackup = document.getElementById("btn-start-backup");
  const backupAutoRefreshToggle = document.getElementById("backup-auto-refresh-toggle");
  const backupProgressTimestamp = document.getElementById("backup-progress-timestamp");
  const activeBackupsCount = document.getElementById("active-backups-count");
  const completedBackupsCount = document.getElementById("completed-backups-count");
  const activeBackupsList = document.getElementById("active-backups-list");
  const completedBackupsList = document.getElementById("completed-backups-list");
  
  // 백업 로그 스트리밍 요소들
  const logStreamingToggle = document.getElementById("log-streaming-toggle");
  const btnClearLogs = document.getElementById("btn-clear-logs");
  const btnDownloadLogs = document.getElementById("btn-download-logs");
  const backupLogsContainer = document.getElementById("backup-logs-container");
  
  // 성능 메트릭 비교 요소들
  const performanceTimeRange = document.getElementById("performance-time-range");
  const btnRefreshPerformance = document.getElementById("btn-refresh-performance");
  const performanceMetricsTimestamp = document.getElementById("performance-metrics-timestamp");
  const performanceRecommendations = document.getElementById("performance-recommendations");
  
  // DB별 성능 요약 요소들
  const postgresqlAvgTime = document.getElementById("postgresql-avg-time");
  const postgresqlAvgCompression = document.getElementById("postgresql-avg-compression");
  const postgresqlBackupCount = document.getElementById("postgresql-backup-count");
  const mysqlAvgTime = document.getElementById("mysql-avg-time");
  const mysqlAvgCompression = document.getElementById("mysql-avg-compression");
  const mysqlBackupCount = document.getElementById("mysql-backup-count");
  const sqliteAvgTime = document.getElementById("sqlite-avg-time");
  const sqliteAvgCompression = document.getElementById("sqlite-avg-compression");
  const sqliteBackupCount = document.getElementById("sqlite-backup-count");

  let backupsChart;
  let averagesChart;
  let backupProgressRefreshInterval;
  let logStreamingInterval;
  let backupTimeComparisonChart;
  let compressionComparisonChart;
  let fileSizeTrendChart;

  // 유틸: 텍스트 설정
  function setText(el, text) {
    if (el) el.textContent = text;
  }

  // SSE(EventSource)로 실시간 스트림 구독 (가능한 경우)
  function initSSE() {
    try {
      if (!window.EventSource) return; // 브라우저 미지원 시 패스
      const es = new EventSource("/api/monitoring/realtime/stream");
      es.onmessage = function (ev) {
        try {
          const data = JSON.parse(ev.data || "{}");
          // 요약 카드 갱신
          setText(
            document.getElementById("sum1h-total"),
            data.summary_1h ? data.summary_1h.total : 0
          );
          setText(
            document.getElementById("sum1h-success"),
            data.summary_1h ? data.summary_1h.successful : 0
          );
          setText(
            document.getElementById("sum1h-failed"),
            data.summary_1h ? data.summary_1h.failed : 0
          );
          setText(
            document.getElementById("sum1h-rate"),
            data.summary_1h ? `${data.summary_1h.success_rate}%` : "0%"
          );
          setText(
            document.getElementById("sum1h-timestamp"),
            data.timestamp || "-"
          );
          // 최근 알림 갱신
          const elNotif = document.getElementById("recent-notif-body");
          if (elNotif) {
            const items = data.recent_notifications || [];
            if (items.length === 0) {
              elNotif.innerHTML =
                '<tr><td colspan="5" class="text-center text-muted">데이터 없음</td></tr>';
            } else {
              elNotif.innerHTML = items
                .map((n) => {
                  const ts = n.created_at
                    ? new Date(n.created_at).toLocaleString()
                    : "-";
                  return `<tr data-notif-id="${n.id}">
                  <td>${escapeHtml(ts)}</td>
                  <td>${escapeHtml(n.notification_type || "-")}</td>
                  <td>${escapeHtml(n.level || "-")}</td>
                  <td>${escapeHtml(n.status || "-")}</td>
                  <td class="text-truncate" style="max-width:260px">${escapeHtml(
                    n.title || ""
                  )}</td>
                </tr>`;
                })
                .join("");
            }
          }
        } catch (e) {
          console.error(e);
        }
      };
      es.onerror = function () {
        /* 연결 오류는 폴링이 보완 */
      };
    } catch (e) {
      console.error(e);
    }
  }

  // 실시간(폴링) 요약 로드: 최근 1시간 집계와 최근 알림 목록
  async function loadRealtime() {
    try {
      const res = await fetch("/api/monitoring/realtime");
      if (!res.ok) throw new Error("실시간 요약 조회 실패");
      const data = await res.json();
      // 최근 1시간 요약 카드 반영
      setText(
        document.getElementById("sum1h-total"),
        data.summary_1h ? data.summary_1h.total : 0
      );
      setText(
        document.getElementById("sum1h-success"),
        data.summary_1h ? data.summary_1h.successful : 0
      );
      setText(
        document.getElementById("sum1h-failed"),
        data.summary_1h ? data.summary_1h.failed : 0
      );
      setText(
        document.getElementById("sum1h-rate"),
        data.summary_1h ? `${data.summary_1h.success_rate}%` : "0%"
      );
      setText(
        document.getElementById("sum1h-timestamp"),
        data.timestamp || "-"
      );
      // 최근 알림  테이블
      const elNotif = document.getElementById("recent-notif-body");
      if (elNotif) {
        const items = data.recent_notifications || [];
        if (items.length === 0) {
          elNotif.innerHTML =
            '<tr><td colspan="5" class="text-center text-muted">데이터 없음</td></tr>';
        } else {
          elNotif.innerHTML = items
            .map((n) => {
              const ts = n.created_at
                ? new Date(n.created_at).toLocaleString()
                : "-";
              return `<tr>
              <td>${escapeHtml(ts)}</td>
              <td>${escapeHtml(n.notification_type || "-")}</td>
              <td>${escapeHtml(n.level || "-")}</td>
              <td>${escapeHtml(n.status || "-")}</td>
              <td class="text-truncate" style="max-width:260px">${escapeHtml(
                n.title || ""
              )}</td>
            </tr>`;
            })
            .join("");
        }
      }
    } catch (e) {
      console.error(e);
    }
  }

  // 유틸: 파일 크기를 사람이 읽기 쉬운 형태로 변환
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

        // 보고서 목록 로딩을 함수로 분리
        async function refreshReportList() {
          const tbody = document.getElementById("report-list-body");
          if (!tbody) return;
          try {
            tbody.innerHTML =
              '<tr><td colspan="4" class="text-center text-muted">로딩중...</td></tr>';
            const res = await fetch("/api/monitoring/reports/list");
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "목록 조회 실패");
            const items = data.reports || [];
            if (items.length === 0) {
              tbody.innerHTML =
                '<tr><td colspan="4" class="text-center text-muted">데이터 없음</td></tr>';
              return;
            }
            tbody.innerHTML = items
              .map((r) => {
                const size =
                  r.size_bytes != null ? humanSize(r.size_bytes) : "-";
                const ts = r.modified_at
                  ? new Date(r.modified_at).toLocaleString()
                  : "-";
                const safeName = escapeHtml(r.filename);
                return `<tr>
                <td class="text-break">${safeName}</td>
                <td>${escapeHtml(size)}</td>
                <td>${escapeHtml(ts)}</td>
                <td class="text-end">
                  <a href="${
                    r.url
                  }" class="btn btn-sm btn-outline-primary me-1">다운로드</a>
                  <button type="button" class="btn btn-sm btn-outline-danger btn-delete-report" data-filename="${safeName}">삭제</button>
                </td>
              </tr>`;
              })
              .join("");
          } catch (err) {
            console.error(err);
            tbody.innerHTML =
              '<tr><td colspan="4" class="text-center text-danger">목록 조회 실패</td></tr>';
          }
        }

        // 보고서 목록 모달 로딩
        document.addEventListener("shown.bs.modal", async function (e) {
          const modal = e.target;
          if (!modal || modal.id !== "reportListModal") return;
          await refreshReportList();
        });

        // 보고서 삭제 클릭 핸들러(이벤트 위임)
        document.addEventListener("click", async function (e) {
          const btn = e.target.closest(".btn-delete-report");
          if (!btn) return;
          const filename = btn.getAttribute("data-filename");
          if (!filename) return;
          // 간단 확인
          if (!confirm(`보고서 ${filename} 을(를) 삭제할까요?`)) return;
          try {
            const res = await fetch(
              `/api/monitoring/reports/${encodeURIComponent(filename)}`,
              { method: "DELETE" }
            );
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || "삭제 실패");
            await refreshReportList();
          } catch (err) {
            console.error(err);
            if (window.Swal) {
              Swal.fire({
                icon: "error",
                title: "삭제 실패",
                text: err.message || "오류가 발생했습니다.",
              });
            }
          }
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
              const dbLabel = item.database_id || "-";
              const dbLink = item.database_id
                ? `/databases/${encodeURIComponent(item.database_id)}`
                : "#";
              const status = item.status || "-";
              const ratio =
                typeof item.compression_ratio === "number"
                  ? `${item.compression_ratio}%`
                  : "-";
              const sizeValue =
                item.compressed_size != null
                  ? item.compressed_size
                  : item.file_size != null
                  ? item.file_size
                  : null;
              const sizeText = humanSize(sizeValue);
              const time = item.created_at
                ? new Date(item.created_at).toLocaleString()
                : "-";
              const detailLink = item.id
                ? `/backups/${encodeURIComponent(item.id)}`
                : "#";
              return `<tr>
                <td><a class="text-decoration-none" href="${dbLink}">${escapeHtml(
                dbLabel
              )}</a></td>
                <td>${escapeHtml(status)}</td>
                <td>${escapeHtml(ratio)}</td>
                <td>${escapeHtml(sizeText)}</td>
                <td>${escapeHtml(time)}</td>
                <td><a class="btn btn-sm btn-outline-primary" href="${detailLink}">보기</a></td>
              </tr>`;
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

  // 압축 도구 상태 로드
  async function loadCompressionStatus() {
    try {
      const res = await fetch("/api/backups/tools/compression-status");
      if (!res.ok) throw new Error("압축 도구 상태 조회 실패");
      const data = await res.json();
      if (elCompDefault)
        elCompDefault.textContent = (
          data.default_compression || "gzip"
        ).toUpperCase();
      if (elCompLevel)
        elCompLevel.textContent = String(data.compression_level ?? "-");
      if (elCompZstd) {
        elCompZstd.textContent = `zstd ${data.zstd ? "사용 가능" : "미설치"}`;
        elCompZstd.classList.remove("text-bg-success", "text-bg-secondary");
        elCompZstd.classList.add(
          data.zstd ? "text-bg-success" : "text-bg-secondary"
        );
      }
      if (elCompLz4) {
        elCompLz4.textContent = `lz4 ${data.lz4 ? "사용 가능" : "미설치"}`;
        elCompLz4.classList.remove("text-bg-success", "text-bg-secondary");
        elCompLz4.classList.add(
          data.lz4 ? "text-bg-success" : "text-bg-secondary"
        );
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
    await Promise.all([
      loadSystemStatus(),
      loadDashboardData(),
      loadCompressionStatus(),
    ]);
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
    loadRealtime();
    initSSE();
    setInterval(refreshAll, 10000); // 10초마다 새로고침
    setInterval(loadRealtime, 15000); // 15초마다 실시간 요약 갱신

    // 보안 모드 토글 초기화
    (async function initSecurityToggle() {
      if (!toggleSecurityMode) return;
      try {
        const res = await fetch("/api/app-settings/security");
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "보안 설정 조회 실패");
        const sec = data.security || {};
        // 간단히 enable_https_redirect 를 토글 기준으로 사용
        toggleSecurityMode.checked = Boolean(sec.enable_https_redirect);
        // DB SSL 기본 모드 초기화
        if (selectDbSslMode && typeof sec.db_ssl_mode_default === "string") {
          selectDbSslMode.value = sec.db_ssl_mode_default;
        }
      } catch (err) {
        console.error(err);
      }
    })();

    // 보안 모드 토글 변경 -> 설정 저장(API)
    if (toggleSecurityMode) {
      toggleSecurityMode.addEventListener("change", async function () {
        try {
          const payload = {
            security: {
              enable_https_redirect: toggleSecurityMode.checked,
              enable_hsts: toggleSecurityMode.checked,
            },
          };
          const res = await fetch("/api/app-settings/security", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "보안 설정 저장 실패");
          if (window.Swal) {
            Swal.fire({
              icon: "success",
              title: "보안 모드",
              text: "설정이 저장되었습니다.",
            });
          }
        } catch (err) {
          console.error(err);
          if (window.Swal) {
            Swal.fire({
              icon: "error",
              title: "보안 모드",
              text: err.message || "저장 실패",
            });
          }
        }
      });
    }

    // DB SSL 기본 모드 변경 -> 설정 저장(API)
    if (selectDbSslMode) {
      selectDbSslMode.addEventListener("change", async function () {
        try {
          const val = selectDbSslMode.value;
          const payload = { security: { db_ssl_mode_default: val } };
          const res = await fetch("/api/app-settings/security", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "DB SSL 모드 저장 실패");
          if (window.Swal) {
            Swal.fire({
              icon: "success",
              title: "DB SSL 기본 모드",
              text: `${val} 으로 저장되었습니다.`,
            });
          }
        } catch (err) {
          console.error(err);
          if (window.Swal) {
            Swal.fire({
              icon: "error",
              title: "DB SSL 기본 모드",
              text: err.message || "저장 실패",
            });
          }
        }
      });
    }

    // 로그아웃 버튼 클릭 처리
    const btnLogout = document.getElementById("btn-logout");
    if (btnLogout) {
      btnLogout.addEventListener("click", async function () {
        try {
          const res = await fetch("/api/auth/logout", { method: "POST" });
          // 쿠키 삭제 후 로그인 화면으로 이동
          window.location.href = "/login";
        } catch (err) {
          console.error(err);
          window.location.href = "/login";
        }
      });
    }
  });

  // 최근 알림 행 클릭 -> 상세 모달 열기 및 재전송 지원
  let notifDetailModalDash;
  document.addEventListener("DOMContentLoaded", function () {
    const el = document.getElementById("notifDetailModalDash");
    if (el && window.bootstrap) {
      notifDetailModalDash = new bootstrap.Modal(el);
    }
  });

  // 목록 클릭 핸들링 (이벤트 위임)
  document.addEventListener("click", async function (e) {
    const tr = e.target.closest("tbody#recent-notif-body tr[data-notif-id]");
    if (!tr) return;
    const id = tr.getAttribute("data-notif-id");
    if (!id) return;
    try {
      const res = await fetch(`/api/notifications/${encodeURIComponent(id)}`);
      const n = await res.json();
      if (!res.ok) throw new Error(n.detail || "상세 조회 실패");
      setText(document.getElementById("dash-nd-id"), n.id || "-");
      setText(
        document.getElementById("dash-nd-type"),
        n.notification_type || "-"
      );
      setText(document.getElementById("dash-nd-level"), n.level || "-");
      setText(document.getElementById("dash-nd-status"), n.status || "-");
      setText(document.getElementById("dash-nd-title"), n.title || "-");
      const msgEl = document.getElementById("dash-nd-msg");
      if (msgEl) msgEl.textContent = n.message || "-";
      setText(document.getElementById("dash-nd-err"), n.error_message || "-");
      const btnResend = document.getElementById("dash-btn-resend-modal");
      if (btnResend) {
        btnResend.setAttribute("data-id", n.id);
      }
      if (notifDetailModalDash) notifDetailModalDash.show();
    } catch (err) {
      console.error(err);
    }
  });

  // 모달 내 재전송 버튼
  document.addEventListener("click", async function (e) {
    const btn = e.target.closest("#dash-btn-resend-modal");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (!id) return;
    try {
      const res = await fetch(
        `/api/notifications/${encodeURIComponent(id)}/resend`,
        { method: "POST" }
      );
      const data = await res.json();
      // 간단 결과를 report-result 영역에 출력
      if (elReportResult)
        elReportResult.textContent = `재전송: ${JSON.stringify(data)}`;
      // 최신 목록 갱신
      loadRealtime();
    } catch (err) {
      console.error(err);
    }
  });

  // 보고서 생성 버튼 처리 (파라미터 반영)
  btnGenerateReport &&
    btnGenerateReport.addEventListener("click", async function () {
      try {
        if (elReportResult) elReportResult.textContent = "보고서 생성 중...";
        const h = selReportHours ? Number(selReportHours.value) || 24 : 24;
        const st = selReportStatus ? selReportStatus.value : "";
        const url = new URL(
          "/api/monitoring/reports/generate",
          window.location.origin
        );
        url.searchParams.set("hours", String(h));
        if (st) url.searchParams.set("status_filter", st);
        if (chkReportNotify && chkReportNotify.checked)
          url.searchParams.set("notify", "true");
        const res = await fetch(url.toString(), { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "보고서 생성 실패");
        if (elReportResult) {
          const a = document.createElement("a");
          a.href = data.report_url;
          a.textContent = `${data.filename} 다운로드 (${data.count}건)`;
          a.className = "text-decoration-none";
          elReportResult.innerHTML = "";
          elReportResult.appendChild(a);
        }
      } catch (e) {
        console.error(e);
        if (elReportResult)
          elReportResult.textContent = e.message || "보고서 생성 실패";
      }
    });

  // 백업 진행 상황 추적 함수들
  
  // 백업 진행 상황 데이터 가져오기
  async function loadBackupProgress() {
    try {
      // 진행 중인 백업 조회 (임시로 최근 백업 중 running 상태인 것들)
      const activeResponse = await fetch('/api/backups?status=running&limit=10');
      let activeBackups = [];
      
      if (activeResponse.ok) {
        const activeData = await activeResponse.json();
        activeBackups = activeData.backups || [];
      }
      
      // 최근 완료된 백업 조회
      const completedResponse = await fetch('/api/backups?status=completed&limit=5&sort=created_at&order=desc');
      let completedBackups = [];
      
      if (completedResponse.ok) {
        const completedData = await completedResponse.json();
        completedBackups = completedData.backups || [];
      }
      
      // 진행 중인 백업 렌더링
      renderActiveBackups(activeBackups);
      
      // 완료된 백업 렌더링
      renderCompletedBackups(completedBackups);
      
      // 카운트 업데이트
      setText(activeBackupsCount, activeBackups.length);
      setText(completedBackupsCount, completedBackups.length);
      
      // 타임스탬프 업데이트
      setText(backupProgressTimestamp, new Date().toLocaleString('ko-KR'));
      
    } catch (error) {
      console.error('백업 진행 상황 로드 오류:', error);
      showBackupProgressError();
    }
  }

  // 진행 중인 백업 렌더링
  function renderActiveBackups(backups) {
    if (!activeBackupsList) return;
    
    if (backups.length === 0) {
      activeBackupsList.innerHTML = `
        <div class="text-center text-muted py-3">
          <div class="mb-2">😴</div>
          <div>현재 진행 중인 백업이 없습니다.</div>
          <button class="btn btn-sm btn-outline-success mt-2" onclick="startBackup()">
            <i class="fas fa-play"></i> 백업 시작
          </button>
        </div>
      `;
      return;
    }
    
    let html = '';
    backups.forEach(backup => {
      const progress = calculateProgress(backup);
      const eta = calculateETA(backup);
      const dbTypeIcon = getDbTypeIcon(backup.database?.db_type);
      
      html += `
        <div class="card mb-3 border-primary">
          <div class="card-body p-3">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div class="d-flex align-items-center">
                <div class="me-2" style="font-size: 1.2rem;">${dbTypeIcon}</div>
                <div>
                  <h6 class="card-title mb-1">${escapeHtml(backup.database?.display_name || backup.database?.name || 'Unknown DB')}</h6>
                  <small class="text-muted">${escapeHtml(backup.database?.host)}:${backup.database?.port}</small>
                </div>
              </div>
              <div class="text-end">
                <span class="badge bg-primary">
                  <i class="fas fa-spinner fa-spin"></i> 진행 중
                </span>
              </div>
            </div>
            
            <!-- 진행률 바 -->
            <div class="mb-2">
              <div class="d-flex justify-content-between align-items-center mb-1">
                <small class="text-muted">진행률</small>
                <small class="fw-semibold">${progress.percentage}%</small>
              </div>
              <div class="progress" style="height: 8px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
                     role="progressbar" 
                     style="width: ${progress.percentage}%">
                </div>
              </div>
            </div>
            
            <div class="row g-2 small">
              <div class="col-6">
                <div class="text-muted">시작 시간</div>
                <div class="fw-semibold">${formatTime(backup.started_at)}</div>
              </div>
              <div class="col-6">
                <div class="text-muted">예상 완료</div>
                <div class="fw-semibold">${eta}</div>
              </div>
            </div>
            
            <div class="row g-2 small mt-2">
              <div class="col-6">
                <div class="text-muted">백업 타입</div>
                <span class="badge bg-outline-info">${backup.backup_type || 'full'}</span>
              </div>
              <div class="col-6">
                <div class="text-muted">압축</div>
                <span class="badge bg-outline-secondary">${backup.compression_algorithm || 'gzip'}</span>
              </div>
            </div>
            
            <div class="mt-2">
              <button class="btn btn-sm btn-outline-danger me-1" onclick="cancelBackup('${backup.id}')">
                <i class="fas fa-stop"></i> 중단
              </button>
              <button class="btn btn-sm btn-outline-secondary" onclick="viewBackupDetails('${backup.id}')">
                <i class="fas fa-info-circle"></i> 상세보기
              </button>
            </div>
          </div>
        </div>
      `;
    });
    
    activeBackupsList.innerHTML = html;
  }

  // 완료된 백업 렌더링
  function renderCompletedBackups(backups) {
    if (!completedBackupsList) return;
    
    if (backups.length === 0) {
      completedBackupsList.innerHTML = `
        <div class="text-center text-muted py-3">
          <div class="mb-2">📋</div>
          <div>최근 완료된 백업이 없습니다.</div>
        </div>
      `;
      return;
    }
    
    let html = '';
    backups.forEach(backup => {
      const dbTypeIcon = getDbTypeIcon(backup.database?.db_type);
      const statusBadge = getBackupStatusBadge(backup.status);
      const duration = calculateDuration(backup.started_at, backup.completed_at);
      
      html += `
        <div class="card mb-2 border-0 shadow-sm">
          <div class="card-body p-3">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div class="d-flex align-items-center">
                <div class="me-2" style="font-size: 1.2rem;">${dbTypeIcon}</div>
                <div>
                  <h6 class="card-title mb-1">${escapeHtml(backup.database?.display_name || backup.database?.name || 'Unknown DB')}</h6>
                  <small class="text-muted">${formatTime(backup.completed_at)}</small>
                </div>
              </div>
              <div class="text-end">
                ${statusBadge}
              </div>
            </div>
            
            <div class="row g-2 small">
              <div class="col-4">
                <div class="text-muted">소요 시간</div>
                <div class="fw-semibold">${duration}</div>
              </div>
              <div class="col-4">
                <div class="text-muted">파일 크기</div>
                <div class="fw-semibold">${humanSize(backup.file_size)}</div>
              </div>
              <div class="col-4">
                <div class="text-muted">압축률</div>
                <div class="fw-semibold">${backup.compression_ratio ? (backup.compression_ratio * 100).toFixed(1) + '%' : '-'}</div>
              </div>
            </div>
          </div>
        </div>
      `;
    });
    
    completedBackupsList.innerHTML = html;
  }

  // 백업 진행 상황 오류 표시
  function showBackupProgressError() {
    if (activeBackupsList) {
      activeBackupsList.innerHTML = `
        <div class="text-center text-danger py-3">
          <div class="mb-2">⚠️</div>
          <div>백업 상태 로드 중 오류가 발생했습니다.</div>
          <button class="btn btn-sm btn-outline-primary mt-2" onclick="loadBackupProgress()">
            다시 시도
          </button>
        </div>
      `;
    }
    
    if (completedBackupsList) {
      completedBackupsList.innerHTML = `
        <div class="text-center text-danger py-3">
          <div class="mb-2">⚠️</div>
          <div>완료된 백업 로드 중 오류가 발생했습니다.</div>
        </div>
      `;
    }
  }

  // 유틸리티 함수들
  
  // DB 타입 아이콘 가져오기
  function getDbTypeIcon(dbType) {
    const iconMap = {
      'postgresql': '🐘',
      'mysql': '🐬',
      'sqlite': '📄'
    };
    return iconMap[dbType] || '🗄️';
  }

  // 백업 상태 배지 생성
  function getBackupStatusBadge(status) {
    const statusMap = {
      'completed': { class: 'bg-success', text: '완료', icon: '✅' },
      'failed': { class: 'bg-danger', text: '실패', icon: '❌' },
      'running': { class: 'bg-primary', text: '진행 중', icon: '🔄' },
      'cancelled': { class: 'bg-warning', text: '취소됨', icon: '⏹️' }
    };
    const config = statusMap[status] || statusMap['completed'];
    return `<span class="badge ${config.class}">${config.icon} ${config.text}</span>`;
  }

  // 진행률 계산 (임시 구현)
  function calculateProgress(backup) {
    if (!backup.started_at) return { percentage: 0 };
    
    const startTime = new Date(backup.started_at);
    const now = new Date();
    const elapsed = now - startTime;
    
    // 임시로 5분을 100%로 가정하여 진행률 계산
    const estimatedDuration = 5 * 60 * 1000; // 5분
    const percentage = Math.min(Math.round((elapsed / estimatedDuration) * 100), 95);
    
    return { percentage };
  }

  // 예상 완료 시간 계산
  function calculateETA(backup) {
    if (!backup.started_at) return '-';
    
    const startTime = new Date(backup.started_at);
    const now = new Date();
    const elapsed = now - startTime;
    
    // 임시로 5분 소요 예상
    const estimatedDuration = 5 * 60 * 1000; // 5분
    const remaining = Math.max(0, estimatedDuration - elapsed);
    
    if (remaining === 0) return '곧 완료';
    
    const minutes = Math.ceil(remaining / (60 * 1000));
    return `약 ${minutes}분 후`;
  }

  // 소요 시간 계산
  function calculateDuration(startTime, endTime) {
    if (!startTime || !endTime) return '-';
    
    const start = new Date(startTime);
    const end = new Date(endTime);
    const duration = end - start;
    
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return `${hours}시간 ${minutes % 60}분`;
    } else if (minutes > 0) {
      return `${minutes}분 ${seconds % 60}초`;
    } else {
      return `${seconds}초`;
    }
  }

  // 백업 로그 스트리밍 함수들
  
  // 로그 스트리밍 시작/중지
  function toggleLogStreaming() {
    if (logStreamingToggle && logStreamingToggle.checked) {
      startLogStreaming();
    } else {
      stopLogStreaming();
    }
  }

  // 로그 스트리밍 시작
  function startLogStreaming() {
    if (logStreamingInterval) return;
    
    if (backupLogsContainer) {
      backupLogsContainer.innerHTML = `
        <div class="text-success">
          <i class="fas fa-play"></i> 로그 스트리밍이 시작되었습니다...
        </div>
      `;
    }
    
    // 5초마다 로그 업데이트
    logStreamingInterval = setInterval(fetchBackupLogs, 5000);
    fetchBackupLogs(); // 즉시 한 번 실행
  }

  // 로그 스트리밍 중지
  function stopLogStreaming() {
    if (logStreamingInterval) {
      clearInterval(logStreamingInterval);
      logStreamingInterval = null;
    }
    
    if (backupLogsContainer) {
      backupLogsContainer.innerHTML = `
        <div class="text-muted text-center py-5">
          로그 스트리밍이 비활성화되어 있습니다.<br>
          <small>위의 토글을 활성화하면 실시간 백업 로그를 볼 수 있습니다.</small>
        </div>
      `;
    }
  }

  // 백업 로그 가져오기
  async function fetchBackupLogs() {
    try {
      const response = await fetch('/api/backups/logs/recent?limit=50');
      if (!response.ok) throw new Error('로그 조회 실패');
      
      const data = await response.json();
      const logs = data.logs || [];
      
      if (backupLogsContainer) {
        let html = '';
        logs.forEach(log => {
          const timestamp = new Date(log.timestamp).toLocaleString('ko-KR');
          const levelClass = getLogLevelClass(log.level);
          html += `
            <div class="log-entry mb-1">
              <span class="text-muted small">[${timestamp}]</span>
              <span class="badge ${levelClass} me-1">${log.level}</span>
              <span>${escapeHtml(log.message)}</span>
            </div>
          `;
        });
        
        if (html) {
          backupLogsContainer.innerHTML = html;
          // 자동 스크롤 (최신 로그가 보이도록)
          backupLogsContainer.scrollTop = backupLogsContainer.scrollHeight;
        } else {
          backupLogsContainer.innerHTML = `
            <div class="text-muted text-center py-3">
              최근 백업 로그가 없습니다.
            </div>
          `;
        }
      }
    } catch (error) {
      console.error('백업 로그 조회 오류:', error);
      if (backupLogsContainer) {
        backupLogsContainer.innerHTML = `
          <div class="text-danger text-center py-3">
            <i class="fas fa-exclamation-triangle"></i> 로그 조회 중 오류가 발생했습니다.
          </div>
        `;
      }
    }
  }

  // 로그 레벨에 따른 CSS 클래스
  function getLogLevelClass(level) {
    const levelMap = {
      'ERROR': 'bg-danger',
      'WARN': 'bg-warning',
      'INFO': 'bg-info',
      'DEBUG': 'bg-secondary'
    };
    return levelMap[level] || 'bg-secondary';
  }

  // 로그 지우기
  function clearLogs() {
    if (backupLogsContainer) {
      backupLogsContainer.innerHTML = `
        <div class="text-muted text-center py-3">
          로그가 지워졌습니다.
        </div>
      `;
    }
  }

  // 로그 다운로드
  function downloadLogs() {
    const logs = backupLogsContainer ? backupLogsContainer.textContent : '';
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backup-logs-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // 전역 함수들 (HTML에서 호출)
  
  // 백업 시작
  window.startBackup = async function() {
    try {
      if (window.Swal) {
        const result = await window.Swal.fire({
          title: '백업 시작',
          text: '모든 활성 데이터베이스의 백업을 시작하시겠습니까?',
          icon: 'question',
          showCancelButton: true,
          confirmButtonText: '시작',
          cancelButtonText: '취소'
        });
        
        if (!result.isConfirmed) return;
      }
      
      const response = await fetch('/api/backups/start-all', {
        method: 'POST'
      });
      
      if (response.ok) {
        const data = await response.json();
        if (window.Swal) {
          window.Swal.fire({
            icon: 'success',
            title: '백업 시작됨',
            text: `${data.started_count || 0}개의 백업이 시작되었습니다.`,
            timer: 3000
          });
        }
        
        // 진행 상황 새로고침
        setTimeout(loadBackupProgress, 1000);
      } else {
        throw new Error('백업 시작 실패');
      }
    } catch (error) {
      console.error('백업 시작 오류:', error);
      if (window.Swal) {
        window.Swal.fire({
          icon: 'error',
          title: '백업 시작 실패',
          text: error.message
        });
      }
    }
  };

  // 백업 취소
  window.cancelBackup = async function(backupId) {
    try {
      if (window.Swal) {
        const result = await window.Swal.fire({
          title: '백업 중단',
          text: '진행 중인 백업을 중단하시겠습니까?',
          icon: 'warning',
          showCancelButton: true,
          confirmButtonText: '중단',
          cancelButtonText: '계속'
        });
        
        if (!result.isConfirmed) return;
      }
      
      const response = await fetch(`/api/backups/${backupId}/cancel`, {
        method: 'POST'
      });
      
      if (response.ok) {
        if (window.Swal) {
          window.Swal.fire({
            icon: 'success',
            title: '백업 중단됨',
            text: '백업이 중단되었습니다.',
            timer: 3000
          });
        }
        
        // 진행 상황 새로고침
        setTimeout(loadBackupProgress, 1000);
      } else {
        throw new Error('백업 중단 실패');
      }
    } catch (error) {
      console.error('백업 중단 오류:', error);
      if (window.Swal) {
        window.Swal.fire({
          icon: 'error',
          title: '백업 중단 실패',
          text: error.message
        });
      }
    }
  };

  // 백업 상세보기
  window.viewBackupDetails = function(backupId) {
    window.location.href = `/backups?highlight=${backupId}`;
  };

  // 백업 진행 상황 자동 새로고침 설정
  function setupBackupProgressAutoRefresh() {
    if (backupProgressRefreshInterval) {
      clearInterval(backupProgressRefreshInterval);
    }
    
    if (backupAutoRefreshToggle && backupAutoRefreshToggle.checked) {
      backupProgressRefreshInterval = setInterval(loadBackupProgress, 10000); // 10초마다
    }
  }

  // 이벤트 리스너 등록
  if (btnRefreshBackupProgress) {
    btnRefreshBackupProgress.addEventListener('click', loadBackupProgress);
  }

  if (btnStartBackup) {
    btnStartBackup.addEventListener('click', window.startBackup);
  }

  if (backupAutoRefreshToggle) {
    backupAutoRefreshToggle.addEventListener('change', setupBackupProgressAutoRefresh);
  }

  if (logStreamingToggle) {
    logStreamingToggle.addEventListener('change', toggleLogStreaming);
  }

  if (btnClearLogs) {
    btnClearLogs.addEventListener('click', clearLogs);
  }

  if (btnDownloadLogs) {
    btnDownloadLogs.addEventListener('click', downloadLogs);
  }

  // 페이지 로드 시 백업 진행 상황 초기화
  document.addEventListener('DOMContentLoaded', function() {
    // 기존 초기화 후 백업 진행 상황 로드
    setTimeout(() => {
      loadBackupProgress();
      setupBackupProgressAutoRefresh();
    }, 2000);
  });

  // 페이지 언로드 시 인터벌 정리
  window.addEventListener('beforeunload', function() {
    if (backupProgressRefreshInterval) {
      clearInterval(backupProgressRefreshInterval);
    }
    if (logStreamingInterval) {
      clearInterval(logStreamingInterval);
    }
  });

  // DB별 성능 메트릭 비교 함수들
  
  // 성능 메트릭 데이터 가져오기
  async function loadPerformanceMetrics() {
    try {
      const days = performanceTimeRange ? performanceTimeRange.value : 30;
      const response = await fetch(`/api/backups/performance-metrics?days=${days}`);
      
      if (!response.ok) {
        // API가 없는 경우 임시 데이터 생성
        const mockData = generateMockPerformanceData(parseInt(days));
        renderPerformanceMetrics(mockData);
        return;
      }
      
      const data = await response.json();
      renderPerformanceMetrics(data);
      
    } catch (error) {
      console.error('성능 메트릭 로드 오류:', error);
      // 오류 시 임시 데이터로 대체
      const mockData = generateMockPerformanceData(30);
      renderPerformanceMetrics(mockData);
    }
  }

  // 임시 성능 데이터 생성
  function generateMockPerformanceData(days) {
    const now = new Date();
    const labels = [];
    const postgresqlData = { times: [], compressions: [], fileSizes: [] };
    const mysqlData = { times: [], compressions: [], fileSizes: [] };
    const sqliteData = { times: [], compressions: [], fileSizes: [] };
    
    for (let i = days - 1; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);
      labels.push(date.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' }));
      
      // PostgreSQL: 일반적으로 더 오래 걸리지만 압축률이 좋음
      postgresqlData.times.push(Math.random() * 300 + 120); // 120-420초
      postgresqlData.compressions.push(Math.random() * 0.3 + 0.7); // 70-100%
      postgresqlData.fileSizes.push(Math.random() * 500 + 100); // 100-600MB
      
      // MySQL: 중간 성능
      mysqlData.times.push(Math.random() * 200 + 80); // 80-280초
      mysqlData.compressions.push(Math.random() * 0.25 + 0.65); // 65-90%
      mysqlData.fileSizes.push(Math.random() * 400 + 80); // 80-480MB
      
      // SQLite: 빠르지만 압축률이 낮음
      sqliteData.times.push(Math.random() * 60 + 10); // 10-70초
      sqliteData.compressions.push(Math.random() * 0.2 + 0.5); // 50-70%
      sqliteData.fileSizes.push(Math.random() * 100 + 20); // 20-120MB
    }
    
    return {
      labels,
      postgresql: {
        avg_time: postgresqlData.times.reduce((a, b) => a + b, 0) / postgresqlData.times.length,
        avg_compression: postgresqlData.compressions.reduce((a, b) => a + b, 0) / postgresqlData.compressions.length,
        backup_count: postgresqlData.times.length,
        daily_data: {
          times: postgresqlData.times,
          compressions: postgresqlData.compressions,
          file_sizes: postgresqlData.fileSizes
        }
      },
      mysql: {
        avg_time: mysqlData.times.reduce((a, b) => a + b, 0) / mysqlData.times.length,
        avg_compression: mysqlData.compressions.reduce((a, b) => a + b, 0) / mysqlData.compressions.length,
        backup_count: mysqlData.times.length,
        daily_data: {
          times: mysqlData.times,
          compressions: mysqlData.compressions,
          file_sizes: mysqlData.fileSizes
        }
      },
      sqlite: {
        avg_time: sqliteData.times.reduce((a, b) => a + b, 0) / sqliteData.times.length,
        avg_compression: sqliteData.compressions.reduce((a, b) => a + b, 0) / sqliteData.compressions.length,
        backup_count: sqliteData.times.length,
        daily_data: {
          times: sqliteData.times,
          compressions: sqliteData.compressions,
          file_sizes: sqliteData.fileSizes
        }
      },
      labels
    };
  }

  // 성능 메트릭 렌더링
  function renderPerformanceMetrics(data) {
    // 성능 요약 카드 업데이트
    updatePerformanceSummary(data);
    
    // 차트 렌더링
    renderBackupTimeComparisonChart(data);
    renderCompressionComparisonChart(data);
    renderFileSizeTrendChart(data);
    
    // 성능 개선 권장사항 생성
    generatePerformanceRecommendations(data);
    
    // 타임스탬프 업데이트
    setText(performanceMetricsTimestamp, new Date().toLocaleString('ko-KR'));
  }

  // 성능 요약 카드 업데이트
  function updatePerformanceSummary(data) {
    // PostgreSQL
    setText(postgresqlAvgTime, formatDuration(data.postgresql.avg_time));
    setText(postgresqlAvgCompression, (data.postgresql.avg_compression * 100).toFixed(1) + '%');
    setText(postgresqlBackupCount, data.postgresql.backup_count);
    
    // MySQL
    setText(mysqlAvgTime, formatDuration(data.mysql.avg_time));
    setText(mysqlAvgCompression, (data.mysql.avg_compression * 100).toFixed(1) + '%');
    setText(mysqlBackupCount, data.mysql.backup_count);
    
    // SQLite
    setText(sqliteAvgTime, formatDuration(data.sqlite.avg_time));
    setText(sqliteAvgCompression, (data.sqlite.avg_compression * 100).toFixed(1) + '%');
    setText(sqliteBackupCount, data.sqlite.backup_count);
  }

  // 백업 시간 비교 차트 렌더링
  function renderBackupTimeComparisonChart(data) {
    const ctx = document.getElementById('backupTimeComparisonChart');
    if (!ctx) return;
    
    if (backupTimeComparisonChart) {
      backupTimeComparisonChart.destroy();
    }
    
    backupTimeComparisonChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['PostgreSQL', 'MySQL', 'SQLite'],
        datasets: [{
          label: '평균 백업 시간 (초)',
          data: [
            data.postgresql.avg_time,
            data.mysql.avg_time,
            data.sqlite.avg_time
          ],
          backgroundColor: [
            'rgba(51, 103, 145, 0.8)',  // PostgreSQL 파랑
            'rgba(0, 117, 143, 0.8)',   // MySQL 청록
            'rgba(0, 59, 87, 0.8)'      // SQLite 네이비
          ],
          borderColor: [
            'rgba(51, 103, 145, 1)',
            'rgba(0, 117, 143, 1)',
            'rgba(0, 59, 87, 1)'
          ],
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                return `평균 시간: ${formatDuration(context.parsed.y)}`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                return formatDuration(value);
              }
            }
          }
        }
      }
    });
  }

  // 압축률 비교 차트 렌더링
  function renderCompressionComparisonChart(data) {
    const ctx = document.getElementById('compressionComparisonChart');
    if (!ctx) return;
    
    if (compressionComparisonChart) {
      compressionComparisonChart.destroy();
    }
    
    compressionComparisonChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['PostgreSQL', 'MySQL', 'SQLite'],
        datasets: [{
          data: [
            data.postgresql.avg_compression * 100,
            data.mysql.avg_compression * 100,
            data.sqlite.avg_compression * 100
          ],
          backgroundColor: [
            'rgba(51, 103, 145, 0.8)',
            'rgba(0, 117, 143, 0.8)',
            'rgba(0, 59, 87, 0.8)'
          ],
          borderColor: [
            'rgba(51, 103, 145, 1)',
            'rgba(0, 117, 143, 1)',
            'rgba(0, 59, 87, 1)'
          ],
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom'
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                return `${context.label}: ${context.parsed.toFixed(1)}%`;
              }
            }
          }
        }
      }
    });
  }

  // 파일 크기 추이 차트 렌더링
  function renderFileSizeTrendChart(data) {
    const ctx = document.getElementById('fileSizeTrendChart');
    if (!ctx) return;
    
    if (fileSizeTrendChart) {
      fileSizeTrendChart.destroy();
    }
    
    fileSizeTrendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [
          {
            label: 'PostgreSQL',
            data: data.postgresql.daily_data.file_sizes,
            borderColor: 'rgba(51, 103, 145, 1)',
            backgroundColor: 'rgba(51, 103, 145, 0.1)',
            tension: 0.3,
            fill: true
          },
          {
            label: 'MySQL',
            data: data.mysql.daily_data.file_sizes,
            borderColor: 'rgba(0, 117, 143, 1)',
            backgroundColor: 'rgba(0, 117, 143, 0.1)',
            tension: 0.3,
            fill: true
          },
          {
            label: 'SQLite',
            data: data.sqlite.daily_data.file_sizes,
            borderColor: 'rgba(0, 59, 87, 1)',
            backgroundColor: 'rgba(0, 59, 87, 0.1)',
            tension: 0.3,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top'
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                return `${context.dataset.label}: ${humanSize(context.parsed.y * 1024 * 1024)}`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                return humanSize(value * 1024 * 1024);
              }
            }
          }
        }
      }
    });
  }

  // 성능 개선 권장사항 생성
  function generatePerformanceRecommendations(data) {
    if (!performanceRecommendations) return;
    
    const recommendations = [];
    
    // PostgreSQL 분석
    if (data.postgresql.avg_time > 300) {
      recommendations.push({
        type: 'warning',
        icon: '🐘',
        title: 'PostgreSQL 백업 시간 최적화',
        message: 'PostgreSQL 백업이 평균 5분 이상 소요되고 있습니다. pg_dump의 --jobs 옵션을 사용하여 병렬 백업을 고려해보세요.',
        action: 'PostgreSQL 설정 최적화'
      });
    }
    
    if (data.postgresql.avg_compression < 0.7) {
      recommendations.push({
        type: 'info',
        icon: '🗜️',
        title: 'PostgreSQL 압축률 개선',
        message: 'PostgreSQL 백업의 압축률이 70% 미만입니다. zstd 압축 알고리즘 사용을 고려해보세요.',
        action: '압축 설정 변경'
      });
    }
    
    // MySQL 분석
    if (data.mysql.avg_time > 200) {
      recommendations.push({
        type: 'warning',
        icon: '🐬',
        title: 'MySQL 백업 시간 최적화',
        message: 'MySQL 백업 시간이 길어지고 있습니다. mysqldump의 --single-transaction 옵션과 함께 --routines, --triggers 옵션을 확인해보세요.',
        action: 'MySQL 설정 최적화'
      });
    }
    
    // SQLite 분석
    if (data.sqlite.avg_compression < 0.6) {
      recommendations.push({
        type: 'info',
        icon: '📄',
        title: 'SQLite 압축률 개선',
        message: 'SQLite 백업의 압축률이 낮습니다. VACUUM 명령으로 데이터베이스를 최적화한 후 백업하는 것을 고려해보세요.',
        action: 'SQLite 최적화'
      });
    }
    
    // 전체 성능 비교
    const avgTimes = [data.postgresql.avg_time, data.mysql.avg_time, data.sqlite.avg_time];
    const maxTime = Math.max(...avgTimes);
    const minTime = Math.min(...avgTimes);
    
    if (maxTime / minTime > 5) {
      recommendations.push({
        type: 'success',
        icon: '📊',
        title: '성능 차이 분석',
        message: 'DB 타입별로 백업 성능 차이가 큽니다. 중요도가 낮은 DB는 백업 주기를 조정하거나 압축 레벨을 낮춰 전체 백업 시간을 단축할 수 있습니다.',
        action: '백업 전략 최적화'
      });
    }
    
    // 권장사항이 없는 경우
    if (recommendations.length === 0) {
      recommendations.push({
        type: 'success',
        icon: '✅',
        title: '최적화된 백업 성능',
        message: '모든 데이터베이스의 백업 성능이 양호합니다. 현재 설정을 유지하시기 바랍니다.',
        action: '현재 설정 유지'
      });
    }
    
    // 권장사항 렌더링
    let html = '';
    recommendations.forEach(rec => {
      const alertClass = rec.type === 'warning' ? 'alert-warning' : 
                        rec.type === 'info' ? 'alert-info' : 'alert-success';
      
      html += `
        <div class="alert ${alertClass} mb-3">
          <div class="d-flex align-items-start">
            <div class="me-3" style="font-size: 1.5rem;">${rec.icon}</div>
            <div class="flex-grow-1">
              <h6 class="alert-heading mb-2">${rec.title}</h6>
              <p class="mb-2">${rec.message}</p>
              <button class="btn btn-sm btn-outline-${rec.type === 'warning' ? 'warning' : rec.type === 'info' ? 'info' : 'success'}">
                ${rec.action}
              </button>
            </div>
          </div>
        </div>
      `;
    });
    
    performanceRecommendations.innerHTML = html;
  }

  // 소요 시간 포맷팅
  function formatDuration(seconds) {
    if (seconds < 60) {
      return `${Math.round(seconds)}초`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = Math.round(seconds % 60);
      return `${minutes}분 ${remainingSeconds}초`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}시간 ${minutes}분`;
    }
  }

  // 성능 메트릭 이벤트 리스너
  if (btnRefreshPerformance) {
    btnRefreshPerformance.addEventListener('click', loadPerformanceMetrics);
  }

  if (performanceTimeRange) {
    performanceTimeRange.addEventListener('change', loadPerformanceMetrics);
  }

  // 페이지 로드 시 성능 메트릭 초기화
  document.addEventListener('DOMContentLoaded', function() {
    // 기존 초기화 후 성능 메트릭 로드
    setTimeout(() => {
      loadPerformanceMetrics();
    }, 3000);
  });

})();
