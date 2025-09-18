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
  
  // DB 타입별 상태 모니터링 요소들
  const btnRefreshDbStatus = document.getElementById("btn-refresh-db-status");
  const autoRefreshToggle = document.getElementById("auto-refresh-toggle");
  const dbStatusTimestamp = document.getElementById("db-status-timestamp");
  const postgresqlCount = document.getElementById("postgresql-count");
  const mysqlCount = document.getElementById("mysql-count");
  const sqliteCount = document.getElementById("sqlite-count");
  const postgresqlDatabases = document.getElementById("postgresql-databases");
  const mysqlDatabases = document.getElementById("mysql-databases");
  const sqliteDatabases = document.getElementById("sqlite-databases");

  let backupsChart;
  let averagesChart;
  let dbStatusRefreshInterval;

  // 유틸: 텍스트 설정
  function setText(el, text) {
    if (el) el.textContent = text;
  }

  // 유틸: 시간 포맷팅
  function formatTime(dateString) {
    if (!dateString || dateString === '-') return '-';
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ko-KR', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateString;
    }
  }

  // 유틸: 상대 시간 표시
  function getRelativeTime(dateString) {
    if (!dateString || dateString === '-') return '-';
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / (1000 * 60));
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return '방금 전';
      if (diffMins < 60) return `${diffMins}분 전`;
      if (diffHours < 24) return `${diffHours}시간 전`;
      if (diffDays < 7) return `${diffDays}일 전`;
      return formatTime(dateString);
    } catch (e) {
      return dateString;
    }
  }

  // 연결 상태 배지 생성
  function getConnectionStatusBadge(status) {
    const statusMap = {
      'connected': { class: 'bg-success', text: '연결됨', icon: '🟢' },
      'error': { class: 'bg-danger', text: '오류', icon: '🔴' },
      'unknown': { class: 'bg-secondary', text: '알 수 없음', icon: '⚪' },
      'testing': { class: 'bg-warning', text: '테스트 중', icon: '🟡' }
    };
    const config = statusMap[status] || statusMap['unknown'];
    return `<span class="badge ${config.class}">${config.icon} ${config.text}</span>`;
  }

  // 백업 성공률 배지 생성
  function getSuccessRateBadge(rate) {
    if (rate === null || rate === undefined || rate === '-') {
      return '<span class="badge bg-secondary">-</span>';
    }
    const numRate = parseFloat(rate);
    let badgeClass = 'bg-secondary';
    if (numRate >= 95) badgeClass = 'bg-success';
    else if (numRate >= 80) badgeClass = 'bg-warning';
    else badgeClass = 'bg-danger';
    
    return `<span class="badge ${badgeClass}">${numRate.toFixed(1)}%</span>`;
  }

  // DB 타입별 상태 데이터 가져오기
  async function loadDbTypeStatus() {
    try {
      const response = await fetch('/api/databases?include_inactive=true');
      if (!response.ok) throw new Error('데이터베이스 목록 조회 실패');
      
      const data = await response.json();
      const databases = data.databases || [];
      
      // DB 타입별로 그룹화
      const groupedDbs = {
        postgresql: databases.filter(db => db.db_type === 'postgresql'),
        mysql: databases.filter(db => db.db_type === 'mysql'),
        sqlite: databases.filter(db => db.db_type === 'sqlite')
      };
      
      // 각 그룹 렌더링
      renderDbGroup('postgresql', groupedDbs.postgresql);
      renderDbGroup('mysql', groupedDbs.mysql);
      renderDbGroup('sqlite', groupedDbs.sqlite);
      
      // 카운트 업데이트
      setText(postgresqlCount, groupedDbs.postgresql.length);
      setText(mysqlCount, groupedDbs.mysql.length);
      setText(sqliteCount, groupedDbs.sqlite.length);
      
      // 타임스탬프 업데이트
      setText(dbStatusTimestamp, new Date().toLocaleString('ko-KR'));
      
    } catch (error) {
      console.error('DB 상태 로드 오류:', error);
      showDbGroupError('postgresql');
      showDbGroupError('mysql');
      showDbGroupError('sqlite');
    }
  }

  // DB 그룹 렌더링
  function renderDbGroup(dbType, databases) {
    const container = document.getElementById(`${dbType}-databases`);
    if (!container) return;
    
    if (databases.length === 0) {
      container.innerHTML = `
        <div class="text-center text-muted py-3">
          <div class="mb-2">📭</div>
          <div>등록된 ${dbType.toUpperCase()} 데이터베이스가 없습니다.</div>
        </div>
      `;
      return;
    }
    
    let html = '';
    databases.forEach(db => {
      const lastBackupTime = getRelativeTime(db.last_backup_time);
      const connectionStatus = getConnectionStatusBadge(db.connection_status);
      const successRate = getSuccessRateBadge(db.backup_success_rate);
      
      html += `
        <div class="card mb-2 border-0 shadow-sm">
          <div class="card-body p-3">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div>
                <h6 class="card-title mb-1">${escapeHtml(db.display_name || db.name)}</h6>
                <small class="text-muted">${escapeHtml(db.host)}:${db.port}</small>
              </div>
              <div class="text-end">
                ${connectionStatus}
              </div>
            </div>
            <div class="row g-2 small">
              <div class="col-6">
                <div class="text-muted">마지막 백업</div>
                <div class="fw-semibold">${lastBackupTime}</div>
              </div>
              <div class="col-6">
                <div class="text-muted">성공률</div>
                <div>${successRate}</div>
              </div>
            </div>
            <div class="row g-2 small mt-2">
              <div class="col-6">
                <div class="text-muted">환경</div>
                <span class="badge bg-outline-secondary">${db.environment}</span>
              </div>
              <div class="col-6">
                <div class="text-muted">우선순위</div>
                <span class="badge bg-outline-${getPriorityColor(db.priority)}">${db.priority}</span>
              </div>
            </div>
            <div class="mt-2">
              <button class="btn btn-sm btn-outline-primary me-1" onclick="testConnection('${db.id}')">
                연결 테스트
              </button>
              <button class="btn btn-sm btn-outline-secondary" onclick="viewDbDetails('${db.id}')">
                상세보기
              </button>
            </div>
          </div>
        </div>
      `;
    });
    
    container.innerHTML = html;
  }

  // DB 그룹 오류 표시
  function showDbGroupError(dbType) {
    const container = document.getElementById(`${dbType}-databases`);
    if (!container) return;
    
    container.innerHTML = `
      <div class="text-center text-danger py-3">
        <div class="mb-2">⚠️</div>
        <div>데이터 로드 중 오류가 발생했습니다.</div>
        <button class="btn btn-sm btn-outline-primary mt-2" onclick="loadDbTypeStatus()">
          다시 시도
        </button>
      </div>
    `;
  }

  // 우선순위 색상 매핑
  function getPriorityColor(priority) {
    const colorMap = {
      'high': 'danger',
      'medium': 'warning', 
      'low': 'success'
    };
    return colorMap[priority] || 'secondary';
  }

  // HTML 이스케이프
  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // 연결 테스트 (전역 함수)
  window.testConnection = async function(dbId) {
    try {
      const response = await fetch(`/api/databases/${dbId}/test-connection`, {
        method: 'POST'
      });
      const result = await response.json();
      
      if (response.ok) {
        if (window.Swal) {
          window.Swal.fire({
            icon: result.status === 'success' ? 'success' : 'error',
            title: '연결 테스트 결과',
            text: `${result.message} (${result.response_time_ms}ms)`,
            timer: 3000
          });
        } else {
          alert(`${result.message} (${result.response_time_ms}ms)`);
        }
        
        // 상태 새로고침
        setTimeout(loadDbTypeStatus, 1000);
      } else {
        throw new Error(result.detail || '연결 테스트 실패');
      }
    } catch (error) {
      console.error('연결 테스트 오류:', error);
      if (window.Swal) {
        window.Swal.fire({
          icon: 'error',
          title: '연결 테스트 실패',
          text: error.message
        });
      } else {
        alert('연결 테스트 실패: ' + error.message);
      }
    }
  };

  // DB 상세보기 (전역 함수)
  window.viewDbDetails = function(dbId) {
    window.location.href = `/databases?highlight=${dbId}`;
  };

  // 자동 새로고침 설정
  function setupAutoRefresh() {
    if (dbStatusRefreshInterval) {
      clearInterval(dbStatusRefreshInterval);
    }
    
    if (autoRefreshToggle && autoRefreshToggle.checked) {
      dbStatusRefreshInterval = setInterval(loadDbTypeStatus, 30000); // 30초마다
    }
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

  // DB 타입별 상태 모니터링 이벤트 리스너
  if (btnRefreshDbStatus) {
    btnRefreshDbStatus.addEventListener('click', loadDbTypeStatus);
  }

  if (autoRefreshToggle) {
    autoRefreshToggle.addEventListener('change', setupAutoRefresh);
  }

  // 페이지 로드 시 DB 상태 초기화
  document.addEventListener('DOMContentLoaded', function() {
    // 기존 초기화 후 DB 상태 로드
    setTimeout(() => {
      loadDbTypeStatus();
      setupAutoRefresh();
    }, 1000);
  });

  // 페이지 언로드 시 인터벌 정리
  window.addEventListener('beforeunload', function() {
    if (dbStatusRefreshInterval) {
      clearInterval(dbStatusRefreshInterval);
    }
  });
})();
