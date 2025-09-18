(function() {
  'use strict';

  // 전역 변수
  let templates = [];
  let databases = [];
  let selectedTemplateId = null;

  // DOM 요소들
  const templateList = document.getElementById('template-list');
  const createTemplateForm = document.getElementById('createTemplateForm');
  const editTemplateForm = document.getElementById('editTemplateForm');
  
  // 모달들
  const createTemplateModal = new bootstrap.Modal(document.getElementById('createTemplateModal'));
  const editTemplateModal = new bootstrap.Modal(document.getElementById('editTemplateModal'));
  const previewTemplateModal = new bootstrap.Modal(document.getElementById('previewTemplateModal'));

  // 초기화
  document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    loadTemplates();
    loadDatabases();
  });

  // 이벤트 리스너 설정
  function initializeEventListeners() {
    // 소스 타입 변경
    document.querySelectorAll('input[name="source-type"]').forEach(radio => {
      radio.addEventListener('change', toggleSourceSection);
    });

    // 템플릿 생성
    document.getElementById('btn-create-template').addEventListener('click', createTemplate);
    
    // 템플릿 수정
    document.getElementById('btn-update-template').addEventListener('click', updateTemplate);
    
    // 템플릿 사용
    document.getElementById('btn-use-template').addEventListener('click', useTemplate);
  }

  // 소스 섹션 토글
  function toggleSourceSection() {
    const sourceType = document.querySelector('input[name="source-type"]:checked').value;
    const existingSection = document.getElementById('existing-db-section');
    const manualSection = document.getElementById('manual-config-section');
    
    if (sourceType === 'existing') {
      existingSection.style.display = 'block';
      manualSection.style.display = 'none';
    } else {
      existingSection.style.display = 'none';
      manualSection.style.display = 'block';
    }
  }

  // 템플릿 목록 로드
  async function loadTemplates() {
    try {
      // 임시 데이터 (실제로는 API에서 가져옴)
      const mockTemplates = [
        {
          id: '1',
          name: 'PostgreSQL 프로덕션',
          description: '프로덕션 환경용 PostgreSQL 설정',
          db_type: 'postgresql',
          environment: 'production',
          is_default: true,
          created_at: '2024-01-15T10:30:00Z',
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
          created_at: '2024-01-10T14:20:00Z',
          config: {
            port: 3306,
            ssl_mode: 'prefer',
            backup_schedule: 'weekly',
            compression: 'lz4'
          }
        },
        {
          id: '3',
          name: 'SQLite 테스트',
          description: '테스트용 SQLite 설정',
          db_type: 'sqlite',
          environment: 'testing',
          is_default: false,
          created_at: '2024-01-08T09:15:00Z',
          config: {
            port: 0,
            backup_schedule: 'manual',
            compression: 'none'
          }
        }
      ];

      templates = mockTemplates;
      renderTemplates();
      
    } catch (error) {
      console.error('템플릿 로드 오류:', error);
      DatabaseUtils.showError('템플릿을 불러오는 중 오류가 발생했습니다.');
    }
  }

  // 데이터베이스 목록 로드
  async function loadDatabases() {
    try {
      const response = await fetch('/api/databases');
      if (response.ok) {
        const data = await response.json();
        databases = data.databases || [];
      } else {
        // 임시 데이터
        databases = [
          { id: '1', name: 'prod-db', display_name: '프로덕션 DB', db_type: 'postgresql' },
          { id: '2', name: 'dev-db', display_name: '개발 DB', db_type: 'mysql' },
          { id: '3', name: 'test-db', display_name: '테스트 DB', db_type: 'sqlite' }
        ];
      }
      
      updateDatabaseSelect();
      
    } catch (error) {
      console.error('데이터베이스 목록 로드 오류:', error);
    }
  }

  // 데이터베이스 선택 옵션 업데이트
  function updateDatabaseSelect() {
    const select = document.getElementById('source-database');
    select.innerHTML = '<option value="">데이터베이스를 선택하세요</option>';
    
    databases.forEach(db => {
      const option = document.createElement('option');
      option.value = db.id;
      option.textContent = `${DatabaseUtils.getDbTypeIcon(db.db_type)} ${db.display_name || db.name}`;
      select.appendChild(option);
    });
  }

  // 템플릿 렌더링
  function renderTemplates() {
    if (templates.length === 0) {
      templateList.innerHTML = `
        <div class="col-12 text-center py-5">
          <div class="text-muted mb-3" style="font-size: 3rem;">📋</div>
          <h5 class="text-muted">저장된 템플릿이 없습니다</h5>
          <p class="text-muted">첫 번째 템플릿을 만들어보세요!</p>
          <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#createTemplateModal">
            <i class="fas fa-plus me-1"></i>템플릿 만들기
          </button>
        </div>
      `;
      return;
    }

    let html = '';
    templates.forEach(template => {
      const dbTypeIcon = DatabaseUtils.getDbTypeIcon(template.db_type);
      const envBadge = DatabaseUtils.getEnvironmentBadge(template.environment);
      const createdDate = new Date(template.created_at).toLocaleDateString('ko-KR');
      
      html += `
        <div class="col-12 col-md-6 col-lg-4">
          <div class="card template-card h-100" data-template-id="${template.id}">
            <div class="card-body">
              <div class="d-flex justify-content-between align-items-start mb-3">
                <div class="d-flex align-items-center">
                  <div class="db-type-badge me-2">${dbTypeIcon}</div>
                  <div>
                    <h6 class="card-title mb-1">${DatabaseUtils.escapeHtml(template.name)}</h6>
                    ${template.is_default ? '<span class="badge bg-warning text-dark">기본</span>' : ''}
                  </div>
                </div>
                <div class="template-actions">
                  <div class="dropdown">
                    <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="dropdown">
                      <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <ul class="dropdown-menu">
                      <li><a class="dropdown-item" href="#" onclick="previewTemplate('${template.id}')">
                        <i class="fas fa-eye me-1"></i>미리보기
                      </a></li>
                      <li><a class="dropdown-item" href="#" onclick="editTemplate('${template.id}')">
                        <i class="fas fa-edit me-1"></i>편집
                      </a></li>
                      <li><a class="dropdown-item" href="#" onclick="duplicateTemplate('${template.id}')">
                        <i class="fas fa-copy me-1"></i>복제
                      </a></li>
                      <li><hr class="dropdown-divider"></li>
                      <li><a class="dropdown-item text-danger" href="#" onclick="deleteTemplate('${template.id}')">
                        <i class="fas fa-trash me-1"></i>삭제
                      </a></li>
                    </ul>
                  </div>
                </div>
              </div>
              
              <p class="card-text text-muted small mb-3">${DatabaseUtils.escapeHtml(template.description || '설명 없음')}</p>
              
              <div class="row g-2 small mb-3">
                <div class="col-6">
                  <div class="text-muted">환경</div>
                  <div>${envBadge}</div>
                </div>
                <div class="col-6">
                  <div class="text-muted">생성일</div>
                  <div>${createdDate}</div>
                </div>
              </div>
              
              <div class="template-preview mb-3">
                <div class="small">
                  <div><strong>포트:</strong> ${template.config.port || '-'}</div>
                  <div><strong>백업:</strong> ${DatabaseUtils.getScheduleText(template.config.backup_schedule)}</div>
                  <div><strong>압축:</strong> ${template.config.compression || 'gzip'}</div>
                </div>
              </div>
              
              <div class="d-grid gap-2">
                <button class="btn btn-primary btn-sm" onclick="useTemplate('${template.id}')">
                  <i class="fas fa-check me-1"></i>이 템플릿 사용
                </button>
              </div>
            </div>
          </div>
        </div>
      `;
    });
    
    templateList.innerHTML = html;
  }

  // 템플릿 생성
  async function createTemplate() {
    try {
      const formData = getCreateFormData();
      
      if (!validateCreateForm(formData)) {
        return;
      }

      // 로딩 표시
      const btn = document.getElementById('btn-create-template');
      const originalText = btn.innerHTML;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>생성 중...';
      btn.disabled = true;

      // API 호출 (임시로 성공 처리)
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // 새 템플릿 추가
      const newTemplate = {
        id: Date.now().toString(),
        name: formData.name,
        description: formData.description,
        db_type: formData.db_type,
        environment: formData.environment,
        is_default: formData.is_default,
        created_at: new Date().toISOString(),
        config: formData.config
      };
      
      templates.push(newTemplate);
      renderTemplates();
      
      // 모달 닫기
      createTemplateModal.hide();
      createTemplateForm.reset();
      
      DatabaseUtils.showSuccess('템플릿이 성공적으로 생성되었습니다.');
      
    } catch (error) {
      console.error('템플릿 생성 오류:', error);
      DatabaseUtils.showError('템플릿 생성 중 오류가 발생했습니다.');
    } finally {
      // 버튼 복원
      const btn = document.getElementById('btn-create-template');
      btn.innerHTML = '<i class="fas fa-save me-1"></i>템플릿 생성';
      btn.disabled = false;
    }
  }

  // 생성 폼 데이터 가져오기
  function getCreateFormData() {
    const sourceType = document.querySelector('input[name="source-type"]:checked').value;
    
    let formData = {
      name: document.getElementById('template-name').value.trim(),
      description: document.getElementById('template-description').value.trim(),
      include_credentials: document.getElementById('include-credentials').checked,
      include_backup_settings: document.getElementById('include-backup-settings').checked,
      is_default: document.getElementById('set-as-default').checked
    };
    
    if (sourceType === 'existing') {
      const dbId = document.getElementById('source-database').value;
      const selectedDb = databases.find(db => db.id === dbId);
      if (selectedDb) {
        formData.db_type = selectedDb.db_type;
        formData.environment = 'production'; // 기본값
        formData.config = {
          port: DatabaseUtils.getDefaultPort(selectedDb.db_type),
          backup_schedule: 'daily',
          compression: 'gzip'
        };
      }
    } else {
      formData.db_type = document.getElementById('manual-db-type').value;
      formData.environment = document.getElementById('manual-environment').value;
      formData.config = {
        port: DatabaseUtils.getDefaultPort(formData.db_type),
        backup_schedule: 'daily',
        compression: 'gzip'
      };
    }
    
    return formData;
  }

  // 생성 폼 검증
  function validateCreateForm(formData) {
    if (!formData.name) {
      DatabaseUtils.showError('템플릿 이름을 입력해주세요.');
      return false;
    }
    
    if (!formData.db_type) {
      DatabaseUtils.showError('데이터베이스 타입을 선택해주세요.');
      return false;
    }
    
    // 중복 이름 체크
    if (templates.some(t => t.name === formData.name)) {
      DatabaseUtils.showError('이미 존재하는 템플릿 이름입니다.');
      return false;
    }
    
    return true;
  }

  // 템플릿 편집
  window.editTemplate = function(templateId) {
    const template = templates.find(t => t.id === templateId);
    if (!template) return;
    
    document.getElementById('edit-template-id').value = template.id;
    document.getElementById('edit-template-name').value = template.name;
    document.getElementById('edit-template-description').value = template.description || '';
    document.getElementById('edit-set-as-default').checked = template.is_default;
    
    editTemplateModal.show();
  };

  // 템플릿 업데이트
  async function updateTemplate() {
    try {
      const templateId = document.getElementById('edit-template-id').value;
      const name = document.getElementById('edit-template-name').value.trim();
      const description = document.getElementById('edit-template-description').value.trim();
      const isDefault = document.getElementById('edit-set-as-default').checked;
      
      if (!name) {
        DatabaseUtils.showError('템플릿 이름을 입력해주세요.');
        return;
      }
      
      // 중복 이름 체크 (자신 제외)
      if (templates.some(t => t.id !== templateId && t.name === name)) {
        DatabaseUtils.showError('이미 존재하는 템플릿 이름입니다.');
        return;
      }
      
      // 템플릿 업데이트
      const template = templates.find(t => t.id === templateId);
      if (template) {
        template.name = name;
        template.description = description;
        template.is_default = isDefault;
        
        // 기본 템플릿 설정 시 다른 템플릿들의 기본 설정 해제
        if (isDefault) {
          templates.forEach(t => {
            if (t.id !== templateId) t.is_default = false;
          });
        }
        
        renderTemplates();
        editTemplateModal.hide();
        DatabaseUtils.showSuccess('템플릿이 업데이트되었습니다.');
      }
      
    } catch (error) {
      console.error('템플릿 업데이트 오류:', error);
      DatabaseUtils.showError('템플릿 업데이트 중 오류가 발생했습니다.');
    }
  }

  // 템플릿 미리보기
  window.previewTemplate = function(templateId) {
    const template = templates.find(t => t.id === templateId);
    if (!template) return;
    
    const previewContent = document.getElementById('template-preview-content');
    const dbTypeIcon = DatabaseUtils.getDbTypeIcon(template.db_type);
    const envBadge = DatabaseUtils.getEnvironmentBadge(template.environment);
    
    previewContent.innerHTML = `
      <div class="row g-3">
        <div class="col-12">
          <div class="d-flex align-items-center mb-3">
            <div class="me-3" style="font-size: 2rem;">${dbTypeIcon}</div>
            <div>
              <h5 class="mb-1">${DatabaseUtils.escapeHtml(template.name)}</h5>
              <p class="text-muted mb-0">${DatabaseUtils.escapeHtml(template.description || '설명 없음')}</p>
            </div>
          </div>
        </div>
        
        <div class="col-md-6">
          <h6>기본 정보</h6>
          <table class="table table-sm">
            <tr><td>DB 타입</td><td>${template.db_type.toUpperCase()}</td></tr>
            <tr><td>환경</td><td>${envBadge}</td></tr>
            <tr><td>포트</td><td>${template.config.port || '-'}</td></tr>
            <tr><td>기본 템플릿</td><td>${template.is_default ? '예' : '아니오'}</td></tr>
          </table>
        </div>
        
        <div class="col-md-6">
          <h6>백업 설정</h6>
          <table class="table table-sm">
            <tr><td>백업 주기</td><td>${DatabaseUtils.getScheduleText(template.config.backup_schedule)}</td></tr>
            <tr><td>압축 방식</td><td>${template.config.compression || 'gzip'}</td></tr>
            <tr><td>SSL 모드</td><td>${template.config.ssl_mode || 'require'}</td></tr>
          </table>
        </div>
        
        <div class="col-12">
          <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            이 템플릿을 사용하면 위 설정이 새 데이터베이스에 자동으로 적용됩니다.
            필요에 따라 개별 설정을 수정할 수 있습니다.
          </div>
        </div>
      </div>
    `;
    
    selectedTemplateId = templateId;
    previewTemplateModal.show();
  };

  // 템플릿 복제
  window.duplicateTemplate = function(templateId) {
    const template = templates.find(t => t.id === templateId);
    if (!template) return;
    
    const newTemplate = {
      ...template,
      id: Date.now().toString(),
      name: template.name + ' (복사본)',
      is_default: false,
      created_at: new Date().toISOString()
    };
    
    templates.push(newTemplate);
    renderTemplates();
    DatabaseUtils.showSuccess('템플릿이 복제되었습니다.');
  };

  // 템플릿 삭제
  window.deleteTemplate = async function(templateId) {
    const template = templates.find(t => t.id === templateId);
    if (!template) return;
    
    const result = await Swal.fire({
      title: '템플릿 삭제',
      text: `"${template.name}" 템플릿을 삭제하시겠습니까?`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: '삭제',
      cancelButtonText: '취소',
      confirmButtonColor: '#dc3545'
    });
    
    if (result.isConfirmed) {
      templates = templates.filter(t => t.id !== templateId);
      renderTemplates();
      DatabaseUtils.showSuccess('템플릿이 삭제되었습니다.');
    }
  };

  // 템플릿 사용
  window.useTemplate = function(templateId) {
    const template = templates.find(t => t.id === templateId);
    if (!template) return;
    
    // 데이터베이스 관리 페이지로 이동하면서 템플릿 ID 전달
    const url = new URL('/databases', window.location.origin);
    url.searchParams.set('template', templateId);
    window.location.href = url.toString();
  };

  // 유틸리티 함수들 (DatabaseUtils 모듈 사용)
  const { 
    getDbTypeIcon, 
    getEnvironmentBadge, 
    getScheduleText, 
    getDefaultPort, 
    escapeHtml, 
    showSuccess, 
    showError 
  } = window.DatabaseUtils;

})();
