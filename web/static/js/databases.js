// 데이터베이스 관리 페이지 스크립트
// - 목록 조회, 추가/수정/삭제, 연결 테스트 연동

(function () {
  "use strict";

  const tbody = document.getElementById("db-tbody");
  const btnRefresh = document.getElementById("btn-refresh");
  const modalEl = document.getElementById("dbModal");
  const modal = modalEl ? new bootstrap.Modal(modalEl) : null;
  // 필터/페이징/토스트/확인 모달 관련 요소
  const filtersForm = document.getElementById("filters-form");
  const btnClear = document.getElementById("btn-clear");
  const paginationEl = document.getElementById("pagination");
  const paginationInfo = document.getElementById("pagination-info");
  // SweetAlert2 사용: Bootstrap Toast/확인 모달 대신 사용
  const toastContainer = null; // 사용 안함
  const confirmModalEl = null; // 사용 안함
  const confirmModal = null;   // 사용 안함
  const confirmModalOk = null; // 사용 안함

  // 폼 요소
  const formId = document.getElementById("form-id");
  const formName = document.getElementById("form-name");
  const formDisplayName = document.getElementById("form-display_name");
  const formDbType = document.getElementById("form-db_type");
  const formHost = document.getElementById("form-host");
  const formPort = document.getElementById("form-port");
  const formDatabaseName = document.getElementById("form-database_name");
  const formUsername = document.getElementById("form-username");
  const formPassword = document.getElementById("form-password");
  const formSslMode = document.getElementById("form-ssl_mode");
  const formEnvironment = document.getElementById("form-environment");
  const formPriority = document.getElementById("form-priority");
  const btnSave = document.getElementById("btn-save");
  const hostHelp = document.getElementById("host-help");
  
  // 템플릿 관련 변수
  let availableTemplates = [];
  let selectedTemplate = null;
  
  // 도움말 및 필수 표시 요소들
  const portHelp = document.getElementById("port-help");
  const portRequired = document.getElementById("port-required");
  const dbnameHelp = document.getElementById("dbname-help");
  const dbnameRequired = document.getElementById("dbname-required");
  const usernameHelp = document.getElementById("username-help");
  const usernameRequired = document.getElementById("username-required");
  const passwordHelp = document.getElementById("password-help");
  const passwordRequired = document.getElementById("password-required");
  const sslHelp = document.getElementById("ssl-help");
  const sslOptional = document.getElementById("ssl-optional");
  
  // 파일 선택기 요소들
  const btnBrowseFile = document.getElementById("btn-browse-file");
  const filePicker = document.getElementById("file-picker");

  // 필터 요소
  const fltQ = document.getElementById("flt-q");
  const fltEnv = document.getElementById("flt-env");
  const fltPriority = document.getElementById("flt-priority");
  const fltStatus = document.getElementById("flt-status");
  const fltIncludeInactive = document.getElementById("flt-include-inactive");
  const fltSort = document.getElementById("flt-sort");
  const fltOrder = document.getElementById("flt-order");
  const fltPageSize = document.getElementById("flt-page-size");

  // 연결 테스트 요소들
  const btnTestConnection = document.getElementById("btn-test-connection");
  const testSpinner = document.getElementById("test-spinner");
  const connectionTestResult = document.getElementById("connection-test-result");
  const testResultAlert = document.getElementById("test-result-alert");
  const testResultIcon = document.getElementById("test-result-icon");
  const testResultTitle = document.getElementById("test-result-title");
  const testResultMessage = document.getElementById("test-result-message");
  const testResultDetails = document.getElementById("test-result-details");

  // 백업 설정 요소들
  const formFullBackupSchedule = document.getElementById("form-full-backup-schedule");
  const formIncrementalBackupSchedule = document.getElementById("form-incremental-backup-schedule");
  const formBackupTime = document.getElementById("form-backup-time");
  const formBackupEnabled = document.getElementById("form-backup-enabled");
  const formCompressionAlgorithm = document.getElementById("form-compression-algorithm");
  const formCompressionLevel = document.getElementById("form-compression-level");
  const formEncryptionEnabled = document.getElementById("form-encryption-enabled");
  const formEncryptionPassword = document.getElementById("form-encryption-password");
  const encryptionPasswordSection = document.getElementById("encryption-password-section");
  const formDailyRetention = document.getElementById("form-daily-retention");
  const formWeeklyRetention = document.getElementById("form-weekly-retention");
  const formMonthlyRetention = document.getElementById("form-monthly-retention");
  const formMaxBackupSize = document.getElementById("form-max-backup-size");
  const formAutoCleanup = document.getElementById("form-auto-cleanup");

  // 페이징 상태
  let state = {
    page: 1,
    pageSize: Number(fltPageSize ? fltPageSize.value : 20) || 20,
    total: 0,
  };

  // 유틸: HTML 이스케이프 (DatabaseUtils 모듈 사용)
  const escapeHtml = window.DatabaseUtils.escapeHtml;

  // 유틸: SweetAlert2 토스트 (DatabaseUtils 모듈 사용)
  const swToast = window.DatabaseUtils.showToast;

  // 유틸: SweetAlert2 확인 (DatabaseUtils 모듈 사용)
  const swConfirm = window.DatabaseUtils.showConfirm;

  // DB 타입 변경 시 포트 자동 설정 및 UI 업데이트
  function handleDbTypeChange() {
    const selectedOption = formDbType.options[formDbType.selectedIndex];
    const defaultPort = selectedOption.getAttribute('data-port');
    const dbType = formDbType.value;
    
    // 기본 포트 자동 설정
    if (defaultPort && formPort) {
      formPort.value = defaultPort;
    }
    
    if (dbType === 'sqlite') {
      configureSQLiteUI();
    } else if (dbType === 'postgresql') {
      configurePostgreSQLUI();
    } else if (dbType === 'mysql') {
      configureMySQLUI();
    } else {
      configureDefaultUI();
    }
  }

  // SQLite 전용 UI 설정
  function configureSQLiteUI() {
    // 호스트 필드 → 파일 경로
    if (formHost) {
      formHost.placeholder = '/path/to/database.db';
      formHost.setAttribute('title', 'SQLite 데이터베이스 파일의 전체 경로를 입력하세요');
      formHost.setAttribute('pattern', '^[/\\\\].*\\.(db|sqlite|sqlite3)$');
    }
    if (hostHelp) {
      hostHelp.innerHTML = 'SQLite 데이터베이스 파일의 전체 경로를 입력하세요. <br><small class="text-muted">예: /data/myapp.db 또는 C:\\data\\myapp.db</small>';
    }
    
    // 파일 선택기 버튼 표시
    if (btnBrowseFile) {
      btnBrowseFile.style.display = 'block';
    }

    // 포트 필드 비활성화
    if (formPort) {
      formPort.disabled = true;
      formPort.value = '0';
      formPort.removeAttribute('required');
    }
    if (portHelp) {
      portHelp.textContent = 'SQLite는 포트를 사용하지 않습니다.';
    }
    if (portRequired) {
      portRequired.style.display = 'none';
    }

    // DB명 필드 비활성화
    if (formDatabaseName) {
      formDatabaseName.disabled = true;
      formDatabaseName.placeholder = '(파일 경로에서 자동 결정)';
      formDatabaseName.removeAttribute('required');
    }
    if (dbnameHelp) {
      dbnameHelp.textContent = '데이터베이스명은 파일 경로에서 자동으로 결정됩니다.';
    }
    if (dbnameRequired) {
      dbnameRequired.style.display = 'none';
    }

    // 사용자명/비밀번호 비활성화
    if (formUsername) {
      formUsername.disabled = true;
      formUsername.placeholder = '(SQLite는 인증 불필요)';
      formUsername.removeAttribute('required');
    }
    if (usernameHelp) {
      usernameHelp.textContent = 'SQLite는 사용자 인증이 필요하지 않습니다.';
    }
    if (usernameRequired) {
      usernameRequired.style.display = 'none';
    }

    if (formPassword) {
      formPassword.disabled = true;
      formPassword.placeholder = '(SQLite는 비밀번호 불필요)';
      formPassword.removeAttribute('required');
    }
    if (passwordHelp) {
      passwordHelp.textContent = 'SQLite는 비밀번호가 필요하지 않습니다.';
    }
    if (passwordRequired) {
      passwordRequired.style.display = 'none';
    }

    // SSL 모드 비활성화
    if (formSslMode) {
      formSslMode.disabled = true;
      formSslMode.value = 'disable';
    }
    if (sslHelp) {
      sslHelp.textContent = 'SQLite는 네트워크 연결을 사용하지 않으므로 SSL이 불필요합니다.';
    }
  }

  // PostgreSQL 전용 UI 설정
  function configurePostgreSQLUI() {
    resetToDefaultUI();
    
    if (formHost) {
      formHost.placeholder = 'localhost 또는 PostgreSQL 서버 주소';
    }
    if (hostHelp) {
      hostHelp.innerHTML = 'PostgreSQL 서버의 호스트 주소를 입력하세요. <br><small class="text-muted">예: localhost, 192.168.1.100, postgres.example.com</small>';
    }
    if (portHelp) {
      portHelp.textContent = 'PostgreSQL 기본 포트는 5432입니다.';
    }
    if (dbnameHelp) {
      dbnameHelp.textContent = '연결할 PostgreSQL 데이터베이스 이름을 입력하세요.';
    }
    if (sslHelp) {
      sslHelp.textContent = 'PostgreSQL SSL/TLS 연결 보안 수준을 선택하세요. 프로덕션 환경에서는 require 이상 권장합니다.';
    }
  }

  // MySQL 전용 UI 설정
  function configureMySQLUI() {
    resetToDefaultUI();
    
    if (formHost) {
      formHost.placeholder = 'localhost 또는 MySQL 서버 주소';
    }
    if (hostHelp) {
      hostHelp.innerHTML = 'MySQL 서버의 호스트 주소를 입력하세요. <br><small class="text-muted">예: localhost, 192.168.1.100, mysql.example.com</small>';
    }
    if (portHelp) {
      portHelp.textContent = 'MySQL 기본 포트는 3306입니다.';
    }
    if (dbnameHelp) {
      dbnameHelp.textContent = '연결할 MySQL 데이터베이스(스키마) 이름을 입력하세요.';
    }
    if (sslHelp) {
      sslHelp.textContent = 'MySQL SSL/TLS 연결 보안 수준을 선택하세요. MySQL 8.0+에서는 기본적으로 SSL이 활성화됩니다.';
    }

    // MySQL SSL 옵션 조정
    if (formSslMode) {
      formSslMode.innerHTML = `
        <option value="DISABLED">DISABLED - SSL 사용 안함</option>
        <option value="PREFERRED">PREFERRED - SSL 선호</option>
        <option value="REQUIRED" selected>REQUIRED - SSL 필수</option>
        <option value="VERIFY_CA">VERIFY_CA - CA 인증서 검증</option>
        <option value="VERIFY_IDENTITY">VERIFY_IDENTITY - 전체 검증</option>
      `;
    }
  }

  // 기본 UI로 리셋
  function resetToDefaultUI() {
    // 모든 필드 활성화
    if (formHost) {
      formHost.disabled = false;
      formHost.removeAttribute('pattern');
      formHost.removeAttribute('title');
    }
    
    // 파일 선택기 버튼 숨기기
    if (btnBrowseFile) {
      btnBrowseFile.style.display = 'none';
    }
    if (formPort) {
      formPort.disabled = false;
      formPort.setAttribute('required', 'required');
    }
    if (formDatabaseName) {
      formDatabaseName.disabled = false;
      formDatabaseName.placeholder = '데이터베이스명';
      formDatabaseName.setAttribute('required', 'required');
    }
    if (formUsername) {
      formUsername.disabled = false;
      formUsername.placeholder = '';
      formUsername.setAttribute('required', 'required');
    }
    if (formPassword) {
      formPassword.disabled = false;
      formPassword.placeholder = '수정 시 공란이면 기존 비밀번호 유지';
    }
    if (formSslMode) {
      formSslMode.disabled = false;
      // PostgreSQL SSL 옵션으로 리셋
      formSslMode.innerHTML = `
        <option value="disable">disable - SSL 사용 안함</option>
        <option value="allow">allow - SSL 허용</option>
        <option value="prefer">prefer - SSL 선호</option>
        <option value="require" selected>require - SSL 필수</option>
        <option value="verify-ca">verify-ca - CA 인증서 검증</option>
        <option value="verify-full">verify-full - 전체 검증</option>
      `;
    }

    // 필수 표시 복원
    if (portRequired) portRequired.style.display = 'inline';
    if (dbnameRequired) dbnameRequired.style.display = 'inline';
    if (usernameRequired) usernameRequired.style.display = 'inline';
    if (passwordRequired) passwordRequired.style.display = 'inline';
  }

  // 기본 UI 설정 (타입 미선택 시)
  function configureDefaultUI() {
    resetToDefaultUI();
    
    if (hostHelp) {
      hostHelp.textContent = '데이터베이스 서버의 호스트 주소를 입력하세요.';
    }
    if (portHelp) {
      portHelp.textContent = '기본 포트가 자동 설정됩니다.';
    }
    if (dbnameHelp) {
      dbnameHelp.textContent = '연결할 데이터베이스 이름을 입력하세요.';
    }
    if (sslHelp) {
      sslHelp.textContent = 'SSL/TLS 연결 보안 수준을 선택하세요.';
    }
  }

  // DB 타입별 유효성 검사
  function validateFormByDbType(payload) {
    // 공통 필수 필드
    if (!payload.name || !payload.display_name || !payload.db_type) {
      return { isValid: false, message: "이름, 표시명, 데이터베이스 타입은 필수입니다." };
    }

    if (payload.db_type === 'sqlite') {
      return validateSQLiteForm(payload);
    } else if (payload.db_type === 'postgresql') {
      return validatePostgreSQLForm(payload);
    } else if (payload.db_type === 'mysql') {
      return validateMySQLForm(payload);
    } else {
      return { isValid: false, message: "지원하지 않는 데이터베이스 타입입니다." };
    }
  }

  // SQLite 유효성 검사
  function validateSQLiteForm(payload) {
    if (!payload.host) {
      return { isValid: false, message: "SQLite 파일 경로를 입력해주세요." };
    }

    // 파일 경로 형식 검사 (간단한 검사)
    const filePath = payload.host.trim();
    if (!filePath.includes('.db') && !filePath.includes('.sqlite') && !filePath.includes('.sqlite3')) {
      return { 
        isValid: false, 
        message: "SQLite 파일 경로는 .db, .sqlite, .sqlite3 확장자를 포함해야 합니다." 
      };
    }

    return { isValid: true };
  }

  // PostgreSQL 유효성 검사
  function validatePostgreSQLForm(payload) {
    if (!payload.host) {
      return { isValid: false, message: "PostgreSQL 서버 호스트를 입력해주세요." };
    }
    if (!payload.database_name) {
      return { isValid: false, message: "PostgreSQL 데이터베이스명을 입력해주세요." };
    }
    if (!payload.username) {
      return { isValid: false, message: "PostgreSQL 사용자명을 입력해주세요." };
    }
    if (!payload.port || payload.port < 1 || payload.port > 65535) {
      return { isValid: false, message: "유효한 포트 번호(1-65535)를 입력해주세요." };
    }

    // 신규 등록 시 비밀번호 필수
    const isNewRecord = !formId.value;
    if (isNewRecord && (!formPassword.value || formPassword.value.trim() === "")) {
      return { isValid: false, message: "PostgreSQL 신규 등록 시 비밀번호는 필수입니다." };
    }

    return { isValid: true };
  }

  // MySQL 유효성 검사
  function validateMySQLForm(payload) {
    if (!payload.host) {
      return { isValid: false, message: "MySQL 서버 호스트를 입력해주세요." };
    }
    if (!payload.database_name) {
      return { isValid: false, message: "MySQL 데이터베이스명을 입력해주세요." };
    }
    if (!payload.username) {
      return { isValid: false, message: "MySQL 사용자명을 입력해주세요." };
    }
    if (!payload.port || payload.port < 1 || payload.port > 65535) {
      return { isValid: false, message: "유효한 포트 번호(1-65535)를 입력해주세요." };
    }

    // 신규 등록 시 비밀번호 필수
    const isNewRecord = !formId.value;
    if (isNewRecord && (!formPassword.value || formPassword.value.trim() === "")) {
      return { isValid: false, message: "MySQL 신규 등록 시 비밀번호는 필수입니다." };
    }

    return { isValid: true };
  }

  // 목록 로드
  async function loadList() {
    try {
      const params = buildQueryParams();
      const res = await fetch(`/api/databases?${params.toString()}`);
      if (!res.ok) throw new Error("DB 목록 로드 실패");
      const data = await res.json();
      const items = data.databases || [];
      state.total = Number(data.total || 0);
      updatePaginationInfo();
      renderPagination();
      if (items.length === 0) {
        tbody.innerHTML =
          '<tr><td colspan="9" class="text-center text-muted">데이터 없음</td></tr>';
        return;
      }
      tbody.innerHTML = items.map((it) => rowTemplate(it)).join("");
    } catch (e) {
      console.error(e);
      tbody.innerHTML =
        '<tr><td colspan="9" class="text-center text-danger">DB 목록 로드 실패</td></tr>';
      swToast(e.message || 'DB 목록 로드 실패', 'error');
    }
  }

  // 배지(상태/환경/우선순위) 일원화 (DatabaseUtils 모듈 사용)
  const statusBadge = window.DatabaseUtils.getStatusBadge;
  const envBadge = window.DatabaseUtils.getEnvironmentBadge;
  const priorityBadge = window.DatabaseUtils.getPriorityBadge;
  
  // DB 타입 배지 (DatabaseUtils 모듈 사용)
  const dbTypeBadge = window.DatabaseUtils.getDbTypeBadge;

  function rowTemplate(it) {
    return `
      <tr>
        <td>${escapeHtml(it.name)}</td>
        <td>${escapeHtml(it.display_name)}</td>
        <td>${dbTypeBadge(it.db_type)}</td>
        <td>${envBadge(it.environment)}</td>
        <td>${priorityBadge(it.priority)}</td>
        <td>${escapeHtml(it.host)}</td>
        <td>${escapeHtml(it.port)}</td>
        <td>${statusBadge(it.connection_status)}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm" role="group">
            <a class="btn btn-outline-secondary" href="/databases/${it.id}">상세</a>
            <button class="btn btn-outline-primary" data-action="test" data-id="${
              it.id
            }">연결 테스트</button>
            ${
              it.is_active === false
                ? `<button class="btn btn-outline-success" data-action="restore" data-id="${it.id}">복구</button>`
                : `<button class="btn btn-outline-secondary" data-action="edit" data-id="${it.id}">수정</button>
               <button class="btn btn-outline-danger" data-action="delete" data-id="${it.id}">삭제</button>`
            }
          </div>
        </td>
      </tr>
    `;
  }

  async function handleAction(e) {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const id = btn.getAttribute("data-id");

    if (action === "test") {
      await testConnection(id);
      await loadList();
      return;
    }

    if (action === "edit") {
      await openEditModal(id);
      return;
    }

    if (action === "delete") {
      const ok = await swConfirm("해당 데이터베이스를 삭제하시겠습니까? (소프트 삭제)");
      if (ok) {
        await deleteDatabase(id);
        await loadList();
      }
      return;
    }

    if (action === "restore") {
      const ok = await swConfirm("해당 데이터베이스를 복구하시겠습니까?");
      if (ok) {
        await restoreDatabase(id);
        await loadList();
      }
      return;
    }
  }

  async function testConnection(id) {
    try {
      const res = await fetch(`/api/databases/${id}/test-connection`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "연결 테스트 실패");
      swToast(`테스트 ${data.status}: ${data.message} (${data.response_time_ms}ms)`, data.status === 'success' ? 'success' : 'error');
    } catch (e) {
      swToast(e.message || '연결 테스트 실패', 'error');
    }
  }

  async function openEditModal(id) {
    try {
      // 서버에 단건 조회 API가 있으므로 활용
      const res = await fetch(`/api/databases/${id}`);
      if (!res.ok) throw new Error("상세 조회 실패");
      const it = await res.json();
      // 모달 값 채우기
      formId.value = it.id;
      formName.value = it.name || "";
      formDisplayName.value = it.display_name || "";
      formDbType.value = it.db_type || "postgresql";
      formHost.value = it.host || "";
      formPort.value = it.port || 5432;
      formDatabaseName.value = it.database_name || "";
      formUsername.value = it.username || "";
      formPassword.value = ""; // 공란이면 비밀번호 유지
      formSslMode.value = it.ssl_mode || "require";
      formEnvironment.value = it.environment || "development";
      formPriority.value = it.priority || "medium";
      
      // 백업 설정 불러오기 (있는 경우)
      if (it.backup_config) {
        const config = it.backup_config;
        if (formFullBackupSchedule) formFullBackupSchedule.value = config.full_backup_schedule || "weekly";
        if (formIncrementalBackupSchedule) formIncrementalBackupSchedule.value = config.incremental_backup_schedule || "daily";
        if (formBackupTime) formBackupTime.value = config.backup_time || "02:00";
        if (formBackupEnabled) formBackupEnabled.checked = config.backup_enabled !== false;
        
        if (config.compression) {
          if (formCompressionAlgorithm) formCompressionAlgorithm.value = config.compression.algorithm || "gzip";
          if (formCompressionLevel) formCompressionLevel.value = config.compression.level || 6;
        }
        
        if (config.encryption) {
          if (formEncryptionEnabled) formEncryptionEnabled.checked = config.encryption.enabled || false;
          // 보안상 암호화 비밀번호는 불러오지 않음
          if (formEncryptionPassword) formEncryptionPassword.value = "";
        }
        
        if (config.retention) {
          if (formDailyRetention) formDailyRetention.value = config.retention.daily || 7;
          if (formWeeklyRetention) formWeeklyRetention.value = config.retention.weekly || 4;
          if (formMonthlyRetention) formMonthlyRetention.value = config.retention.monthly || 12;
          if (formMaxBackupSize) formMaxBackupSize.value = config.retention.max_backup_size_gb || 100;
          if (formAutoCleanup) formAutoCleanup.checked = config.retention.auto_cleanup !== false;
        }
      }
      
      // DB 타입에 따른 UI 업데이트
      handleDbTypeChange();
      
      // 연결 테스트 결과 숨기기
      if (connectionTestResult) {
        connectionTestResult.style.display = 'none';
      }
      
      // 연결 테스트 버튼 상태 리셋
      setTestingState(false);
      
      // 암호화 UI 업데이트
      handleEncryptionToggle();
      
      document.getElementById("dbModalTitle").textContent = "Edit Database";
      modal && modal.show();
    } catch (e) {
      swToast(e.message || '상세 조회 실패', 'error');
    }
  }

  btnSave && btnSave.addEventListener("click", saveDatabase);

  async function saveDatabase() {
    try {
      const payload = {
        name: formName.value.trim(),
        display_name: formDisplayName.value.trim(),
        db_type: formDbType.value,
        host: formHost.value.trim(),
        port: Number(formPort.value) || 5432,
        database_name: formDatabaseName.value.trim(),
        username: formUsername.value.trim(),
        // password는 신규 시 필수, 수정 시 공란이면 전송하지 않음
        ssl_mode: formSslMode.value.trim(),
        environment: formEnvironment.value,
        priority: formPriority.value,
        // 백업 설정 추가
        backup_config: {
          full_backup_schedule: formFullBackupSchedule ? formFullBackupSchedule.value : "weekly",
          incremental_backup_schedule: formIncrementalBackupSchedule ? formIncrementalBackupSchedule.value : "daily",
          backup_time: formBackupTime ? formBackupTime.value : "02:00",
          backup_enabled: formBackupEnabled ? formBackupEnabled.checked : true,
          compression: {
            algorithm: formCompressionAlgorithm ? formCompressionAlgorithm.value : "gzip",
            level: formCompressionLevel ? Number(formCompressionLevel.value) : 6
          },
          encryption: {
            enabled: formEncryptionEnabled ? formEncryptionEnabled.checked : false,
            password: (formEncryptionEnabled && formEncryptionEnabled.checked && formEncryptionPassword) ? formEncryptionPassword.value : null
          },
          retention: {
            daily: formDailyRetention ? Number(formDailyRetention.value) : 7,
            weekly: formWeeklyRetention ? Number(formWeeklyRetention.value) : 4,
            monthly: formMonthlyRetention ? Number(formMonthlyRetention.value) : 12,
            max_backup_size_gb: formMaxBackupSize ? Number(formMaxBackupSize.value) : 100,
            auto_cleanup: formAutoCleanup ? formAutoCleanup.checked : true
          }
        }
      };

      // DB 타입별 유효성 검사
      const validationResult = validateFormByDbType(payload);
      if (!validationResult.isValid) {
        swToast(validationResult.message, 'warning');
        return;
      }

      const id = formId.value;
      if (id) {
        // 수정: 비밀번호 공란이면 포함하지 않음
        const updateBody = { ...payload };
        if (formPassword.value && formPassword.value.trim() !== "") {
          updateBody.password = formPassword.value;
        }
        const res = await fetch(`/api/databases/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updateBody),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "수정 실패");
        swToast('성공적으로 수정되었습니다.', 'success');
      } else {
        // 추가: 비밀번호 필수 검증
        if (!formPassword.value || formPassword.value.trim() === "") {
          swToast('신규 등록 시 비밀번호는 필수입니다.', 'warning');
          return;
        }
        const createBody = { ...payload, password: formPassword.value };
        const res = await fetch(`/api/databases/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(createBody),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "등록 실패");
        swToast('성공적으로 등록되었습니다.', 'success');
      }

      modal && modal.hide();
      await loadList();
    } catch (e) {
      swToast(e.message || '작업 실패', 'error');
    }
  }

  async function deleteDatabase(id) {
    try {
      const res = await fetch(`/api/databases/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "삭제 실패");
      swToast('성공적으로 삭제되었습니다.', 'success');
    } catch (e) {
      swToast(e.message || '삭제 실패', 'error');
    }
  }

  async function restoreDatabase(id) {
    try {
      const res = await fetch(`/api/databases/${id}/restore`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '복구 실패');
      swToast('성공적으로 복구되었습니다.', 'success');
    } catch (e) {
      swToast(e.message || '복구 실패', 'error');
    }
  }

  // 쿼리 파라미터 구성(검색/필터/정렬/페이징)
  function buildQueryParams() {
    const params = new URLSearchParams();
    params.set("page", String(state.page));
    params.set("page_size", String(state.pageSize));
    if (fltQ && fltQ.value.trim()) params.set("q", fltQ.value.trim());
    if (fltEnv && fltEnv.value) params.set("environment", fltEnv.value);
    if (fltPriority && fltPriority.value)
      params.set("priority", fltPriority.value);
    if (fltStatus && fltStatus.value)
      params.set("status_filter", fltStatus.value);
    if (fltIncludeInactive && fltIncludeInactive.checked)
      params.set("include_inactive", "true");
    if (fltSort && fltSort.value) params.set("sort", fltSort.value);
    if (fltOrder && fltOrder.value) params.set("order", fltOrder.value);
    return params;
  }

  // 페이지 정보 갱신 및 페이지네이션 렌더링
  function updatePaginationInfo() {
    if (!paginationInfo) return;
    const start = (state.page - 1) * state.pageSize + 1;
    const end = Math.min(state.page * state.pageSize, state.total || 0);
    paginationInfo.textContent = state.total
      ? `${start}-${end} / ${state.total}`
      : "0 / 0";
  }

  function renderPagination() {
    if (!paginationEl) return;
    const totalPages = Math.max(
      1,
      Math.ceil((state.total || 0) / state.pageSize)
    );
    const cur = Math.min(state.page, totalPages);
    state.page = cur;
    let html = "";
    function pageItem(p, label = null, disabled = false, active = false) {
      const cls = `page-item ${disabled ? "disabled" : ""} ${
        active ? "active" : ""
      }`;
      const text = label || String(p);
      return `<li class="${cls}"><a class="page-link" href="#" data-page="${p}">${text}</a></li>`;
    }
    html += pageItem(Math.max(1, cur - 1), "«", cur === 1, false);
    const windowSize = 5;
    const start = Math.max(1, cur - Math.floor(windowSize / 2));
    const end = Math.min(totalPages, start + windowSize - 1);
    for (let p = start; p <= end; p++)
      html += pageItem(p, null, false, p === cur);
    html += pageItem(
      Math.min(totalPages, cur + 1),
      "»",
      cur === totalPages,
      false
    );
    paginationEl.innerHTML = html;
  }

  document.addEventListener("click", handleAction);
  
  // DB 타입 변경 이벤트 리스너
  formDbType && formDbType.addEventListener("change", handleDbTypeChange);
  
  // 연결 테스트 버튼 이벤트 리스너
  btnTestConnection && btnTestConnection.addEventListener("click", testDatabaseConnection);
  
  // 암호화 옵션 변경 이벤트 리스너
  formEncryptionEnabled && formEncryptionEnabled.addEventListener("change", handleEncryptionToggle);
  
  // 암호화 옵션에 따른 UI 업데이트
  function handleEncryptionToggle() {
    if (formEncryptionEnabled && encryptionPasswordSection) {
      if (formEncryptionEnabled.checked) {
        encryptionPasswordSection.style.display = 'block';
        if (formEncryptionPassword) {
          formEncryptionPassword.setAttribute('required', 'required');
        }
      } else {
        encryptionPasswordSection.style.display = 'none';
        if (formEncryptionPassword) {
          formEncryptionPassword.removeAttribute('required');
          formEncryptionPassword.value = '';
        }
      }
    }
  }
  
  // 파일 선택기 이벤트 리스너
  btnBrowseFile && btnBrowseFile.addEventListener("click", () => {
    filePicker && filePicker.click();
  });
  
  filePicker && filePicker.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (formHost) {
        // 웹 환경에서는 실제 파일 경로를 얻을 수 없으므로 파일명만 표시
        formHost.value = file.name;
        formHost.setAttribute('title', `선택된 파일: ${file.name}`);
      }
      swToast(`파일 선택됨: ${file.name}`, 'info');
    }
  });
  
  btnRefresh &&
    btnRefresh.addEventListener("click", () => {
      state.page = 1;
      loadList();
    });
  filtersForm &&
    filtersForm.addEventListener("submit", (e) => {
      e.preventDefault();
      state.page = 1;
      state.pageSize = Number(fltPageSize.value) || 20;
      loadList();
    });
  btnClear &&
    btnClear.addEventListener("click", () => {
      if (fltQ) fltQ.value = "";
      if (fltEnv) fltEnv.value = "";
      if (fltPriority) fltPriority.value = "";
      if (fltStatus) fltStatus.value = "";
      if (fltIncludeInactive) fltIncludeInactive.checked = false;
      if (fltSort) fltSort.value = "display_name";
      if (fltOrder) fltOrder.value = "asc";
      if (fltPageSize) fltPageSize.value = "20";
      state.page = 1;
      state.pageSize = 20;
      loadList();
    });
  paginationEl &&
    paginationEl.addEventListener("click", (e) => {
      const a = e.target.closest("a.page-link");
      if (!a) return;
      e.preventDefault();
      const p = Number(a.getAttribute("data-page"));
      if (!isNaN(p) && p >= 1) {
        state.page = p;
        loadList();
      }
    });

  // 새 DB 추가 모달 초기화
  function resetModal() {
    // 기본 설정 필드 리셋
    formId.value = "";
    formName.value = "";
    formDisplayName.value = "";
    formDbType.value = "";
    formHost.value = "";
    formPort.value = "5432";
    formDatabaseName.value = "";
    formUsername.value = "";
    formPassword.value = "";
    formSslMode.value = "require";
    formEnvironment.value = "development";
    formPriority.value = "medium";
    
    // 백업 설정 필드 리셋
    if (formFullBackupSchedule) formFullBackupSchedule.value = "weekly";
    if (formIncrementalBackupSchedule) formIncrementalBackupSchedule.value = "daily";
    if (formBackupTime) formBackupTime.value = "02:00";
    if (formBackupEnabled) formBackupEnabled.checked = true;
    if (formCompressionAlgorithm) formCompressionAlgorithm.value = "gzip";
    if (formCompressionLevel) formCompressionLevel.value = "6";
    if (formEncryptionEnabled) formEncryptionEnabled.checked = false;
    if (formEncryptionPassword) formEncryptionPassword.value = "";
    if (formDailyRetention) formDailyRetention.value = "7";
    if (formWeeklyRetention) formWeeklyRetention.value = "4";
    if (formMonthlyRetention) formMonthlyRetention.value = "12";
    if (formMaxBackupSize) formMaxBackupSize.value = "100";
    if (formAutoCleanup) formAutoCleanup.checked = true;
    
    // 기본 UI 상태로 리셋
    configureDefaultUI();
    
    // 연결 테스트 결과 숨기기
    if (connectionTestResult) {
      connectionTestResult.style.display = 'none';
    }
    
      // 연결 테스트 버튼 상태 리셋
    setTestingState(false);
    
    // 암호화 UI 리셋
    handleEncryptionToggle();
    
    document.getElementById("dbModalTitle").textContent = "새 데이터베이스 추가";
  }

  // 새 DB 추가 버튼 이벤트
  const btnAddDb = document.querySelector('[data-bs-target="#dbModal"]');
  btnAddDb && btnAddDb.addEventListener("click", resetModal);

  // 템플릿 관련 함수들
  
  // 템플릿 목록 로드
  async function loadTemplates() {
    try {
      // 임시 템플릿 데이터 (실제로는 API에서 가져옴)
      availableTemplates = [
        {
          id: '1',
          name: 'PostgreSQL 프로덕션',
          description: '프로덕션 환경용 PostgreSQL 설정',
          db_type: 'postgresql',
          environment: 'production',
          is_default: true,
          config: {
            port: 5432,
            ssl_mode: 'require',
            backup_schedule: 'daily',
            compression: 'gzip'
          }
        },
        {
          id: '2',
          name: 'MySQL 개발환경',
          description: '개발 환경용 MySQL 설정',
          db_type: 'mysql',
          environment: 'development',
          is_default: false,
          config: {
            port: 3306,
            ssl_mode: 'prefer',
            backup_schedule: 'weekly',
            compression: 'lz4'
          }
        }
      ];
    } catch (error) {
      console.error('템플릿 로드 오류:', error);
    }
  }

  // URL에서 템플릿 파라미터 확인
  function checkUrlTemplate() {
    const urlParams = new URLSearchParams(window.location.search);
    const templateId = urlParams.get('template');
    
    if (templateId) {
      // 템플릿 자동 적용
      applyTemplateById(templateId);
      // URL에서 파라미터 제거
      const newUrl = window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }

  // 템플릿 적용 버튼 이벤트
  const btnApplyTemplate = document.getElementById('btn-apply-template');
  btnApplyTemplate && btnApplyTemplate.addEventListener('click', showTemplateSelectModal);

  // 템플릿 선택 모달 표시
  function showTemplateSelectModal() {
    const modal = new bootstrap.Modal(document.getElementById('templateSelectModal'));
    renderTemplateSelectList();
    modal.show();
  }

  // 템플릿 선택 목록 렌더링
  function renderTemplateSelectList() {
    const container = document.getElementById('template-select-list');
    if (!container) return;

    if (availableTemplates.length === 0) {
      container.innerHTML = `
        <div class="col-12 text-center py-4">
          <div class="text-muted mb-3" style="font-size: 2rem;">📋</div>
          <h6 class="text-muted">사용 가능한 템플릿이 없습니다</h6>
          <p class="text-muted small">템플릿을 먼저 생성해주세요.</p>
          <a href="/database-templates" class="btn btn-primary btn-sm">
            <i class="fas fa-plus me-1"></i>템플릿 만들기
          </a>
        </div>
      `;
      return;
    }

    let html = '';
    availableTemplates.forEach(template => {
      const dbTypeIcon = DatabaseUtils.getDbTypeIcon(template.db_type);
      const envBadge = DatabaseUtils.getEnvironmentBadge(template.environment);
      
      html += `
        <div class="col-12 col-md-6">
          <div class="card template-select-card h-100" style="cursor: pointer;" onclick="applyTemplate('${template.id}')">
            <div class="card-body">
              <div class="d-flex align-items-center mb-2">
                <div class="me-2" style="font-size: 1.5rem;">${dbTypeIcon}</div>
                <div class="flex-grow-1">
                  <h6 class="card-title mb-1">${DatabaseUtils.escapeHtml(template.name)}</h6>
                  ${template.is_default ? '<span class="badge bg-warning text-dark">기본</span>' : ''}
                </div>
              </div>
              <p class="card-text text-muted small mb-2">${DatabaseUtils.escapeHtml(template.description || '설명 없음')}</p>
              <div class="row g-2 small">
                <div class="col-6">
                  <div class="text-muted">환경</div>
                  <div>${envBadge}</div>
                </div>
                <div class="col-6">
                  <div class="text-muted">포트</div>
                  <div>${template.config.port || '-'}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  // 템플릿 적용
  window.applyTemplate = function(templateId) {
    const template = availableTemplates.find(t => t.id === templateId);
    if (!template) return;

    applyTemplateToForm(template);
    
    // 모달 닫기
    const modal = bootstrap.Modal.getInstance(document.getElementById('templateSelectModal'));
    modal && modal.hide();
    
    swToast(`"${template.name}" 템플릿이 적용되었습니다.`, 'success');
  };

  // ID로 템플릿 적용
  function applyTemplateById(templateId) {
    const template = availableTemplates.find(t => t.id === templateId);
    if (template) {
      applyTemplateToForm(template);
      swToast(`"${template.name}" 템플릿이 자동으로 적용되었습니다.`, 'info');
    }
  }

  // 템플릿을 폼에 적용
  function applyTemplateToForm(template) {
    // 기본 설정 적용
    if (formDbType) formDbType.value = template.db_type;
    if (formEnvironment) formEnvironment.value = template.environment;
    if (formPort) formPort.value = template.config.port || DatabaseUtils.getDefaultPort(template.db_type);
    if (formSslMode) formSslMode.value = template.config.ssl_mode || 'require';
    
    // 백업 설정 적용
    if (formFullBackupSchedule) formFullBackupSchedule.value = template.config.backup_schedule || 'daily';
    if (formCompressionAlgorithm) formCompressionAlgorithm.value = template.config.compression || 'gzip';
    
    // DB 타입 변경 이벤트 트리거
    handleDbTypeChange();
    
    selectedTemplate = template;
  }

  // 유틸리티 함수들 (DatabaseUtils 모듈 사용)
  const getDbTypeIcon = window.DatabaseUtils.getDbTypeIcon;
  const getEnvironmentBadge = window.DatabaseUtils.getEnvironmentBadge;
  const getDefaultPort = window.DatabaseUtils.getDefaultPort;

  // 연결 테스트 상태 설정
  function setTestingState(isTesting) {
    if (btnTestConnection && testSpinner) {
      if (isTesting) {
        btnTestConnection.disabled = true;
        testSpinner.style.display = 'inline-block';
        btnTestConnection.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>테스트 중...';
      } else {
        btnTestConnection.disabled = false;
        testSpinner.style.display = 'none';
        btnTestConnection.innerHTML = '<i class="fas fa-plug me-1"></i>연결 테스트';
      }
    }
  }

  // 연결 테스트 수행
  async function testDatabaseConnection() {
    try {
      // 현재 폼 데이터로 연결 테스트
      const payload = {
        db_type: formDbType.value,
        host: formHost.value.trim(),
        port: Number(formPort.value) || 5432,
        database_name: formDatabaseName.value.trim(),
        username: formUsername.value.trim(),
        password: formPassword.value || 'test', // 비밀번호가 비어있으면 임시 값
        ssl_mode: formSslMode.value
      };

      // DB 타입별 유효성 검사
      const validationResult = validateFormByDbType(payload);
      if (!validationResult.isValid) {
        showTestResult(false, '유효성 검사 실패', validationResult.message);
        return;
      }

      setTestingState(true);
      showTestResult(null, '연결 테스트 중...', '데이터베이스 연결을 확인하고 있습니다.');

      // 임시 API 호출 (실제로는 서버에서 처리)
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // 성공 시뮤레이션
      const success = Math.random() > 0.3; // 70% 성공률
      
      if (success) {
        showTestResult(true, '연결 성공', `${payload.db_type.toUpperCase()} 데이터베이스에 성공적으로 연결되었습니다.`);
      } else {
        showTestResult(false, '연결 실패', '데이터베이스 연결에 실패했습니다. 설정을 확인해주세요.');
      }
      
    } catch (error) {
      console.error('연결 테스트 오류:', error);
      showTestResult(false, '연결 테스트 오류', error.message || '예상치 못한 오류가 발생했습니다.');
    } finally {
      setTestingState(false);
    }
  }

  // 연결 테스트 결과 표시
  function showTestResult(success, title, message, details = null) {
    if (!connectionTestResult) return;
    
    connectionTestResult.style.display = 'block';
    
    if (testResultAlert) {
      testResultAlert.className = `alert ${success === true ? 'alert-success' : success === false ? 'alert-danger' : 'alert-info'} mb-0`;
    }
    
    if (testResultIcon) {
      testResultIcon.className = `fas ${success === true ? 'fa-check-circle text-success' : success === false ? 'fa-times-circle text-danger' : 'fa-info-circle text-info'}`;
    }
    
    if (testResultTitle) {
      testResultTitle.textContent = title;
    }
    
    if (testResultMessage) {
      testResultMessage.textContent = message;
    }
    
    if (testResultDetails && details) {
      testResultDetails.textContent = details;
      testResultDetails.style.display = 'block';
    } else if (testResultDetails) {
      testResultDetails.style.display = 'none';
    }
  }

})();
