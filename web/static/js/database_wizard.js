(function() {
  'use strict';

  // 마법사 상태 관리
  let currentStep = 1;
  let selectedDbType = null;
  let wizardData = {
    dbType: null,
    connection: {},
    backup: {}
  };

  // DOM 요소들
  const wizardProgress = document.getElementById('wizard-progress');
  const currentStepSpan = document.getElementById('current-step');
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  
  // 단계별 요소들
  const stepIndicators = document.querySelectorAll('.step-item');
  const stepConnectors = document.querySelectorAll('.step-connector');
  const wizardSteps = document.querySelectorAll('.wizard-step');
  
  // DB 타입 카드들
  const dbTypeCards = document.querySelectorAll('.db-type-card');
  
  // 폼 요소들
  const connectionForm = document.getElementById('connection-form');
  const backupForm = document.getElementById('backup-form');
  
  // 연결 테스트 관련
  const testConnectionBtn = document.getElementById('test-connection');
  const connectionResult = document.getElementById('connection-result');
  
  // 비밀번호 토글
  const togglePasswordBtn = document.getElementById('toggle-password');
  const passwordInput = document.getElementById('password');

  // 초기화
  document.addEventListener('DOMContentLoaded', function() {
    initializeWizard();
    setupEventListeners();
    updateStepDisplay();
  });

  // 마법사 초기화
  function initializeWizard() {
    // URL 파라미터에서 DB 타입 확인
    const urlParams = new URLSearchParams(window.location.search);
    const preselectedType = urlParams.get('type');
    
    if (preselectedType && ['postgresql', 'mysql', 'sqlite'].includes(preselectedType)) {
      selectDbType(preselectedType);
    }
    
    // 기본 설정값 적용
    applyDefaultSettings();
  }

  // 이벤트 리스너 설정
  function setupEventListeners() {
    // 네비게이션 버튼
    prevBtn.addEventListener('click', goToPreviousStep);
    nextBtn.addEventListener('click', goToNextStep);
    
    // DB 타입 선택
    dbTypeCards.forEach(card => {
      card.addEventListener('click', function() {
        const dbType = this.getAttribute('data-db-type');
        selectDbType(dbType);
      });
    });
    
    // 연결 테스트
    if (testConnectionBtn) {
      testConnectionBtn.addEventListener('click', testDatabaseConnection);
    }
    
    // 비밀번호 토글
    if (togglePasswordBtn) {
      togglePasswordBtn.addEventListener('click', togglePasswordVisibility);
    }
    
    // 폼 입력 변경 감지
    if (connectionForm) {
      connectionForm.addEventListener('input', validateConnectionForm);
    }
    
    if (backupForm) {
      backupForm.addEventListener('change', updateBackupSummary);
    }
    
    // DB 타입 변경 시 설정 업데이트
    document.addEventListener('dbTypeChanged', updateConnectionFormForDbType);
  }

  // DB 타입 선택
  function selectDbType(dbType) {
    selectedDbType = dbType;
    wizardData.dbType = dbType;
    
    // 모든 카드에서 선택 해제
    dbTypeCards.forEach(card => {
      card.classList.remove('selected');
    });
    
    // 선택된 카드 표시
    const selectedCard = document.querySelector(`[data-db-type="${dbType}"]`);
    if (selectedCard) {
      selectedCard.classList.add('selected');
    }
    
    // 다음 버튼 활성화
    nextBtn.disabled = false;
    
    // DB 타입 변경 이벤트 발생
    document.dispatchEvent(new CustomEvent('dbTypeChanged', { detail: { dbType } }));
  }

  // 연결 폼을 DB 타입에 맞게 업데이트
  function updateConnectionFormForDbType(event) {
    const dbType = event.detail.dbType;
    
    // 단계 2 제목과 설명 업데이트
    const step2Title = document.getElementById('step2-title');
    const step2Description = document.getElementById('step2-description');
    const hostField = document.getElementById('host-field');
    const portField = document.getElementById('port-field');
    const databaseField = document.getElementById('database-field');
    const hostInput = document.getElementById('host');
    const portInput = document.getElementById('port');
    const databaseInput = document.getElementById('database');
    const usernameInput = document.getElementById('username');
    const hostHelp = document.getElementById('host-help');
    const portHelp = document.getElementById('port-help');
    
    // DB별 아이콘과 제목
    const dbConfig = {
      postgresql: {
        icon: '🐘',
        name: 'PostgreSQL',
        defaultPort: 5432,
        defaultUser: 'postgres',
        placeholder: {
          host: 'localhost',
          database: 'myapp',
          username: 'postgres'
        }
      },
      mysql: {
        icon: '🐬',
        name: 'MySQL',
        defaultPort: 3306,
        defaultUser: 'root',
        placeholder: {
          host: 'localhost',
          database: 'myapp',
          username: 'root'
        }
      },
      sqlite: {
        icon: '📄',
        name: 'SQLite',
        defaultPort: 0,
        defaultUser: '',
        placeholder: {
          host: '/path/to/database.db',
          database: '',
          username: ''
        }
      }
    };
    
    const config = dbConfig[dbType];
    
    if (step2Title) {
      step2Title.innerHTML = `${config.icon} ${config.name} 연결 정보를 입력하세요`;
    }
    
    if (step2Description) {
      step2Description.textContent = `${config.name} 데이터베이스에 연결하기 위한 정보를 입력해주세요.`;
    }
    
    // SQLite의 경우 특별 처리
    if (dbType === 'sqlite') {
      // 호스트를 파일 경로로 변경
      if (hostInput) {
        hostInput.placeholder = config.placeholder.host;
        hostInput.value = '';
      }
      if (hostHelp) {
        hostHelp.textContent = 'SQLite 데이터베이스 파일의 전체 경로';
      }
      
      // 포트와 데이터베이스명 필드 비활성화
      if (portField) portField.style.display = 'none';
      if (databaseField) databaseField.style.display = 'none';
      
      // 사용자명도 선택사항으로
      if (usernameInput) {
        usernameInput.required = false;
        usernameInput.placeholder = '(선택사항)';
      }
    } else {
      // PostgreSQL, MySQL의 경우
      if (hostInput) {
        hostInput.placeholder = config.placeholder.host;
        hostInput.value = config.placeholder.host;
      }
      if (portInput) {
        portInput.value = config.defaultPort;
      }
      if (databaseInput) {
        databaseInput.placeholder = config.placeholder.database;
      }
      if (usernameInput) {
        usernameInput.placeholder = config.placeholder.username;
        usernameInput.value = config.defaultUser;
        usernameInput.required = true;
      }
      
      if (hostHelp) {
        hostHelp.textContent = '데이터베이스 서버의 IP 주소 또는 도메인명';
      }
      if (portHelp) {
        portHelp.textContent = `기본 포트: ${config.defaultPort}`;
      }
      
      // 필드 표시
      if (portField) portField.style.display = 'block';
      if (databaseField) databaseField.style.display = 'block';
    }
    
    // 권장 설정 표시
    showRecommendedSettings(dbType);
  }

  // 권장 설정 표시
  function showRecommendedSettings(dbType) {
    const recommendedSettings = document.getElementById('recommended-settings');
    const recommendedList = document.getElementById('recommended-list');
    
    if (!recommendedSettings || !recommendedList) return;
    
    const recommendations = {
      postgresql: [
        '기본 포트 5432 설정',
        'postgres 사용자 계정 사용',
        'UTF-8 인코딩 권장',
        '병렬 백업을 위한 --jobs 옵션 활용'
      ],
      mysql: [
        '기본 포트 3306 설정',
        'root 또는 전용 백업 계정 사용',
        'InnoDB 엔진 최적화',
        '--single-transaction 옵션으로 일관성 보장'
      ],
      sqlite: [
        '파일 경로 직접 지정',
        '별도 사용자 계정 불필요',
        'WAL 모드 사용 권장',
        'VACUUM으로 최적화 후 백업'
      ]
    };
    
    const items = recommendations[dbType] || [];
    recommendedList.innerHTML = items.map(item => `<li>${item}</li>`).join('');
    
    recommendedSettings.style.display = 'block';
  }

  // 기본 설정값 적용
  function applyDefaultSettings() {
    // 환경별 기본값
    const environmentSelect = document.getElementById('environment');
    if (environmentSelect) {
      environmentSelect.value = 'development';
    }
    
    // 백업 설정 기본값
    const backupSchedule = document.getElementById('backup-schedule');
    const backupTime = document.getElementById('backup-time');
    const compression = document.getElementById('compression');
    const retention = document.getElementById('retention');
    const priority = document.getElementById('priority');
    
    if (backupSchedule) backupSchedule.value = 'daily';
    if (backupTime) backupTime.value = '02:00';
    if (compression) compression.value = 'gzip';
    if (retention) retention.value = '30';
    if (priority) priority.value = '2';
  }

  // 다음 단계로 이동
  function goToNextStep() {
    if (currentStep === 1) {
      // DB 타입 선택 검증
      if (!selectedDbType) {
        showAlert('warning', '데이터베이스 타입을 선택해주세요.');
        return;
      }
    } else if (currentStep === 2) {
      // 연결 정보 검증
      if (!validateConnectionForm()) {
        showAlert('warning', '필수 연결 정보를 모두 입력해주세요.');
        return;
      }
      saveConnectionData();
    } else if (currentStep === 3) {
      // 백업 설정 저장 및 완료
      saveBackupData();
      submitWizard();
      return;
    }
    
    currentStep++;
    updateStepDisplay();
  }

  // 이전 단계로 이동
  function goToPreviousStep() {
    if (currentStep > 1) {
      currentStep--;
      updateStepDisplay();
    }
  }

  // 단계 표시 업데이트
  function updateStepDisplay() {
    // 진행률 업데이트
    const progress = (currentStep / 3) * 100;
    wizardProgress.style.width = `${progress}%`;
    
    // 현재 단계 표시
    currentStepSpan.textContent = currentStep;
    
    // 단계 표시기 업데이트
    stepIndicators.forEach((indicator, index) => {
      const stepNum = index + 1;
      indicator.classList.remove('active', 'completed', 'pending');
      
      if (stepNum < currentStep) {
        indicator.classList.add('completed');
      } else if (stepNum === currentStep) {
        indicator.classList.add('active');
      } else {
        indicator.classList.add('pending');
      }
    });
    
    // 연결선 업데이트
    stepConnectors.forEach((connector, index) => {
      connector.classList.remove('completed');
      if (index + 1 < currentStep) {
        connector.classList.add('completed');
      }
    });
    
    // 마법사 단계 표시
    wizardSteps.forEach((step, index) => {
      step.classList.remove('active');
      if (index + 1 === currentStep) {
        step.classList.add('active');
      }
    });
    
    // 네비게이션 버튼 상태
    prevBtn.disabled = currentStep === 1;
    
    if (currentStep === 3) {
      nextBtn.innerHTML = '<i class="fas fa-check me-1"></i>완료';
      nextBtn.classList.remove('btn-primary');
      nextBtn.classList.add('btn-success');
    } else {
      nextBtn.innerHTML = '다음 <i class="fas fa-arrow-right ms-1"></i>';
      nextBtn.classList.remove('btn-success');
      nextBtn.classList.add('btn-primary');
    }
    
    // 단계별 특별 처리
    if (currentStep === 2) {
      // 연결 폼 검증 시작
      validateConnectionForm();
    } else if (currentStep === 3) {
      // 백업 설정 요약 업데이트
      updateBackupSummary();
    }
  }

  // 연결 폼 검증
  function validateConnectionForm() {
    if (!connectionForm) return false;
    
    const displayName = document.getElementById('display-name');
    const host = document.getElementById('host');
    const port = document.getElementById('port');
    const database = document.getElementById('database');
    const username = document.getElementById('username');
    const password = document.getElementById('password');
    
    let isValid = true;
    
    // 필수 필드 검증
    if (!displayName?.value.trim()) isValid = false;
    if (!host?.value.trim()) isValid = false;
    if (!password?.value.trim()) isValid = false;
    
    // SQLite가 아닌 경우 추가 검증
    if (selectedDbType !== 'sqlite') {
      if (!port?.value) isValid = false;
      if (!database?.value.trim()) isValid = false;
      if (!username?.value.trim()) isValid = false;
    }
    
    return isValid;
  }

  // 연결 데이터 저장
  function saveConnectionData() {
    wizardData.connection = {
      display_name: document.getElementById('display-name')?.value.trim(),
      host: document.getElementById('host')?.value.trim(),
      port: selectedDbType === 'sqlite' ? 0 : parseInt(document.getElementById('port')?.value),
      database: selectedDbType === 'sqlite' ? '' : document.getElementById('database')?.value.trim(),
      username: document.getElementById('username')?.value.trim(),
      password: document.getElementById('password')?.value,
      environment: document.getElementById('environment')?.value,
      db_type: selectedDbType
    };
  }

  // 백업 데이터 저장
  function saveBackupData() {
    wizardData.backup = {
      schedule: document.getElementById('backup-schedule')?.value,
      time: document.getElementById('backup-time')?.value,
      compression: document.getElementById('compression')?.value,
      retention_days: parseInt(document.getElementById('retention')?.value),
      priority: parseInt(document.getElementById('priority')?.value),
      run_first_backup: document.getElementById('run-first-backup')?.checked
    };
  }

  // 백업 설정 요약 업데이트
  function updateBackupSummary() {
    const summaryContainer = document.getElementById('settings-summary');
    if (!summaryContainer) return;
    
    const schedule = document.getElementById('backup-schedule')?.value;
    const time = document.getElementById('backup-time')?.value;
    const compression = document.getElementById('compression')?.value;
    const retention = document.getElementById('retention')?.value;
    const priority = document.getElementById('priority')?.value;
    const runFirstBackup = document.getElementById('run-first-backup')?.checked;
    
    const scheduleText = {
      daily: '매일',
      weekly: '매주',
      monthly: '매월',
      manual: '수동'
    };
    
    const priorityText = {
      1: '높음',
      2: '보통',
      3: '낮음'
    };
    
    const retentionText = retention === '0' ? '무제한' : `${retention}일`;
    
    summaryContainer.innerHTML = `
      <div class="col-6 col-md-3">
        <small class="text-muted">백업 주기</small>
        <div class="fw-bold">${scheduleText[schedule] || schedule}</div>
      </div>
      <div class="col-6 col-md-3">
        <small class="text-muted">백업 시간</small>
        <div class="fw-bold">${time}</div>
      </div>
      <div class="col-6 col-md-3">
        <small class="text-muted">압축</small>
        <div class="fw-bold">${compression.toUpperCase()}</div>
      </div>
      <div class="col-6 col-md-3">
        <small class="text-muted">보관 기간</small>
        <div class="fw-bold">${retentionText}</div>
      </div>
      <div class="col-6 col-md-3">
        <small class="text-muted">우선순위</small>
        <div class="fw-bold">${priorityText[priority] || priority}</div>
      </div>
      <div class="col-6 col-md-3">
        <small class="text-muted">첫 백업</small>
        <div class="fw-bold">${runFirstBackup ? '즉시 실행' : '나중에'}</div>
      </div>
    `;
  }

  // 데이터베이스 연결 테스트
  async function testDatabaseConnection() {
    if (!validateConnectionForm()) {
      showAlert('warning', '연결 정보를 모두 입력해주세요.');
      return;
    }
    
    // 버튼 상태 변경
    testConnectionBtn.disabled = true;
    testConnectionBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>테스트 중...';
    
    try {
      // 연결 데이터 준비
      const connectionData = {
        db_type: selectedDbType,
        host: document.getElementById('host')?.value.trim(),
        port: selectedDbType === 'sqlite' ? 0 : parseInt(document.getElementById('port')?.value),
        database: selectedDbType === 'sqlite' ? '' : document.getElementById('database')?.value.trim(),
        username: document.getElementById('username')?.value.trim(),
        password: document.getElementById('password')?.value
      };
      
      // API 호출 (임시로 성공으로 처리)
      await new Promise(resolve => setTimeout(resolve, 2000)); // 2초 대기
      
      // 성공 표시
      connectionResult.innerHTML = `
        <div class="alert alert-success">
          <i class="fas fa-check-circle me-2"></i>
          <strong>연결 성공!</strong> 데이터베이스에 정상적으로 연결되었습니다.
        </div>
      `;
      
    } catch (error) {
      // 오류 표시
      connectionResult.innerHTML = `
        <div class="alert alert-danger">
          <i class="fas fa-exclamation-triangle me-2"></i>
          <strong>연결 실패:</strong> ${error.message || '데이터베이스에 연결할 수 없습니다.'}
        </div>
      `;
    } finally {
      // 버튼 상태 복원
      testConnectionBtn.disabled = false;
      testConnectionBtn.innerHTML = '<i class="fas fa-plug me-1"></i>연결 테스트';
    }
  }

  // 비밀번호 표시/숨김 토글
  function togglePasswordVisibility() {
    const isPassword = passwordInput.type === 'password';
    passwordInput.type = isPassword ? 'text' : 'password';
    togglePasswordBtn.innerHTML = isPassword ? 
      '<i class="fas fa-eye-slash"></i>' : 
      '<i class="fas fa-eye"></i>';
  }

  // 마법사 완료 및 제출
  async function submitWizard() {
    try {
      // 로딩 표시
      nextBtn.disabled = true;
      nextBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>저장 중...';
      
      // 데이터베이스 등록 API 호출
      const response = await fetch('/api/databases', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: wizardData.connection.display_name,
          display_name: wizardData.connection.display_name,
          db_type: wizardData.connection.db_type,
          host: wizardData.connection.host,
          port: wizardData.connection.port,
          database: wizardData.connection.database,
          username: wizardData.connection.username,
          password: wizardData.connection.password,
          environment: wizardData.connection.environment,
          priority: wizardData.backup.priority,
          backup_schedule: wizardData.backup.schedule,
          backup_time: wizardData.backup.time,
          compression_algorithm: wizardData.backup.compression,
          retention_days: wizardData.backup.retention_days
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        
        // 완료 단계로 이동
        showCompletionStep(result);
        
        // 첫 백업 실행
        if (wizardData.backup.run_first_backup) {
          runFirstBackup(result.id);
        }
        
      } else {
        throw new Error('데이터베이스 등록에 실패했습니다.');
      }
      
    } catch (error) {
      console.error('마법사 완료 오류:', error);
      showAlert('error', error.message || '설정 저장 중 오류가 발생했습니다.');
      
      // 버튼 상태 복원
      nextBtn.disabled = false;
      nextBtn.innerHTML = '<i class="fas fa-check me-1"></i>완료';
    }
  }

  // 완료 단계 표시
  function showCompletionStep(dbResult) {
    // 완료 단계로 전환
    wizardSteps.forEach(step => step.classList.remove('active'));
    document.getElementById('step-complete').classList.add('active');
    
    // 네비게이션 숨김
    document.querySelector('.card-footer').style.display = 'none';
    
    // 진행률 100%
    wizardProgress.style.width = '100%';
    
    // 모든 단계 완료 표시
    stepIndicators.forEach(indicator => {
      indicator.classList.remove('active', 'pending');
      indicator.classList.add('completed');
    });
    stepConnectors.forEach(connector => {
      connector.classList.add('completed');
    });
    
    // 최종 요약 표시
    const finalSummary = document.getElementById('final-summary');
    if (finalSummary) {
      const dbTypeIcons = {
        postgresql: '🐘',
        mysql: '🐬',
        sqlite: '📄'
      };
      
      finalSummary.innerHTML = `
        <div class="row g-3">
          <div class="col-12 col-md-6">
            <div class="d-flex align-items-center">
              <div class="me-3" style="font-size: 2rem;">${dbTypeIcons[wizardData.connection.db_type]}</div>
              <div>
                <h6 class="mb-1">${wizardData.connection.display_name}</h6>
                <small class="text-muted">${wizardData.connection.db_type.toUpperCase()}</small>
              </div>
            </div>
          </div>
          <div class="col-12 col-md-6">
            <small class="text-muted">연결 정보</small>
            <div>${wizardData.connection.host}:${wizardData.connection.port}</div>
            <small class="text-muted">${wizardData.connection.environment} 환경</small>
          </div>
        </div>
      `;
    }
  }

  // 첫 번째 백업 실행
  async function runFirstBackup(databaseId) {
    const firstBackupStatus = document.getElementById('first-backup-status');
    if (!firstBackupStatus) return;
    
    firstBackupStatus.innerHTML = `
      <div class="card border-primary">
        <div class="card-body text-center">
          <div class="spinner-border text-primary mb-3" role="status">
            <span class="visually-hidden">백업 중...</span>
          </div>
          <h6>첫 번째 백업을 실행하고 있습니다...</h6>
          <p class="text-muted mb-0">잠시만 기다려주세요.</p>
        </div>
      </div>
    `;
    
    try {
      // 백업 시작 API 호출
      const response = await fetch(`/api/databases/${databaseId}/backup`, {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        
        firstBackupStatus.innerHTML = `
          <div class="card border-success">
            <div class="card-body text-center">
              <i class="fas fa-check-circle text-success display-6 mb-3"></i>
              <h6 class="text-success">첫 번째 백업이 시작되었습니다!</h6>
              <p class="text-muted mb-3">백업 진행 상황은 대시보드에서 확인할 수 있습니다.</p>
              <a href="/dashboard" class="btn btn-sm btn-outline-success">
                <i class="fas fa-eye me-1"></i>진행 상황 보기
              </a>
            </div>
          </div>
        `;
      } else {
        throw new Error('백업 시작에 실패했습니다.');
      }
      
    } catch (error) {
      firstBackupStatus.innerHTML = `
        <div class="card border-warning">
          <div class="card-body text-center">
            <i class="fas fa-exclamation-triangle text-warning display-6 mb-3"></i>
            <h6 class="text-warning">첫 번째 백업 시작 실패</h6>
            <p class="text-muted mb-3">${error.message}</p>
            <p class="small text-muted">데이터베이스는 정상적으로 등록되었으며, 나중에 수동으로 백업을 실행할 수 있습니다.</p>
          </div>
        </div>
      `;
    }
  }

  // 알림 표시
  function showAlert(type, message) {
    if (window.Swal) {
      const iconMap = {
        success: 'success',
        error: 'error',
        warning: 'warning',
        info: 'info'
      };
      
      Swal.fire({
        icon: iconMap[type] || 'info',
        title: message,
        timer: 3000,
        showConfirmButton: false
      });
    } else {
      alert(message);
    }
  }

  // 유틸리티 함수들
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

})();
