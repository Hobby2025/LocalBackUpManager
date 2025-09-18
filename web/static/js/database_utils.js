/**
 * 데이터베이스 관리 공통 유틸리티 모듈
 * - DB 타입별 아이콘, 환경 배지, 기본 포트 등 공통 기능 제공
 * - HTML 이스케이프, 알림 표시 등 유틸리티 함수 제공
 */

(function(window) {
  'use strict';

  // 네임스페이스 생성
  window.DatabaseUtils = window.DatabaseUtils || {};

  /**
   * DB 타입별 아이콘 반환
   * @param {string} dbType - 데이터베이스 타입 (postgresql, mysql, sqlite)
   * @returns {string} 아이콘 이모지
   */
  function getDbTypeIcon(dbType) {
    const icons = {
      postgresql: '🐘',
      mysql: '🐬',
      sqlite: '📄'
    };
    return icons[dbType] || '🗄️';
  }

  /**
   * 환경별 배지 HTML 반환
   * @param {string} environment - 환경 (production, staging, development, testing)
   * @returns {string} 배지 HTML
   */
  function getEnvironmentBadge(environment) {
    const badges = {
      production: '<span class="badge bg-danger">프로덕션</span>',
      staging: '<span class="badge bg-warning">스테이징</span>',
      development: '<span class="badge bg-info">개발</span>',
      testing: '<span class="badge bg-secondary">테스트</span>'
    };
    return badges[environment] || `<span class="badge bg-light text-dark">${environment}</span>`;
  }

  /**
   * DB 타입별 기본 포트 반환
   * @param {string} dbType - 데이터베이스 타입
   * @returns {number} 기본 포트 번호
   */
  function getDefaultPort(dbType) {
    const ports = {
      postgresql: 5432,
      mysql: 3306,
      sqlite: 0
    };
    return ports[dbType] || 0;
  }

  /**
   * HTML 이스케이프 처리
   * @param {string} text - 이스케이프할 텍스트
   * @returns {string} 이스케이프된 HTML
   */
  function escapeHtml(text) {
    if (text == null) return "";
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  /**
   * 백업 스케줄 텍스트 반환
   * @param {string} schedule - 스케줄 (daily, weekly, monthly, manual)
   * @returns {string} 한글 스케줄 텍스트
   */
  function getScheduleText(schedule) {
    const schedules = {
      daily: '매일',
      weekly: '매주',
      monthly: '매월',
      manual: '수동'
    };
    return schedules[schedule] || schedule;
  }

  /**
   * 성공 메시지 표시
   * @param {string} message - 표시할 메시지
   */
  function showSuccess(message) {
    if (window.Swal) {
      window.Swal.fire({
        icon: 'success',
        title: '성공',
        text: message,
        timer: 3000,
        showConfirmButton: false
      });
    } else {
      alert(message);
    }
  }

  /**
   * 오류 메시지 표시
   * @param {string} message - 표시할 메시지
   */
  function showError(message) {
    if (window.Swal) {
      window.Swal.fire({
        icon: 'error',
        title: '오류',
        text: message
      });
    } else {
      alert(message);
    }
  }

  /**
   * 정보 메시지 표시
   * @param {string} message - 표시할 메시지
   */
  function showInfo(message) {
    if (window.Swal) {
      window.Swal.fire({
        icon: 'info',
        title: '정보',
        text: message,
        timer: 3000,
        showConfirmButton: false
      });
    } else {
      alert(message);
    }
  }

  /**
   * 경고 메시지 표시
   * @param {string} message - 표시할 메시지
   */
  function showWarning(message) {
    if (window.Swal) {
      window.Swal.fire({
        icon: 'warning',
        title: '경고',
        text: message
      });
    } else {
      alert(message);
    }
  }

  /**
   * SweetAlert2 토스트 메시지 표시
   * @param {string} message - 표시할 메시지
   * @param {string} icon - 아이콘 타입 (success, error, warning, info)
   */
  function showToast(message, icon = 'success') {
    if (window.Swal) {
      const toast = window.Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 2500,
        timerProgressBar: true,
      });
      toast.fire({ icon: icon, title: message });
    } else {
      alert(message);
    }
  }

  /**
   * 확인 대화상자 표시
   * @param {string} message - 확인 메시지
   * @returns {Promise<boolean>} 사용자 선택 결과
   */
  function showConfirm(message) {
    return new Promise((resolve) => {
      if (window.Swal) {
        window.Swal.fire({
          title: message,
          icon: 'question',
          showCancelButton: true,
          confirmButtonText: '확인',
          cancelButtonText: '취소',
        }).then((result) => {
          resolve(result.isConfirmed);
        });
      } else {
        const ok = confirm(message);
        resolve(ok);
      }
    });
  }

  /**
   * DB 타입별 배지 HTML 반환
   * @param {string} dbType - 데이터베이스 타입
   * @returns {string} 배지 HTML
   */
  function getDbTypeBadge(dbType) {
    const typeMap = {
      postgresql: { icon: "🐘", color: "primary", name: "PostgreSQL" },
      mysql: { icon: "🐬", color: "info", name: "MySQL" },
      sqlite: { icon: "📄", color: "secondary", name: "SQLite" }
    };
    const type = typeMap[(dbType || "").toLowerCase()] || { 
      icon: "❓", 
      color: "secondary", 
      name: dbType || "Unknown" 
    };
    return `<span class="badge text-bg-${type.color}">${type.icon} ${type.name}</span>`;
  }

  /**
   * 상태별 배지 HTML 반환
   * @param {string} status - 상태
   * @returns {string} 배지 HTML
   */
  function getStatusBadge(status) {
    const s = (status || "").toLowerCase();
    const cls = s === "connected" ? "success" : s === "error" ? "danger" : "secondary";
    return `<span class="badge text-bg-${cls}">${escapeHtml(status || "알 수 없음")}</span>`;
  }

  /**
   * 우선순위별 배지 HTML 반환
   * @param {string} priority - 우선순위
   * @returns {string} 배지 HTML
   */
  function getPriorityBadge(priority) {
    const map = { high: "danger", medium: "primary", low: "secondary" };
    const cls = map[(priority || "").toLowerCase()] || "secondary";
    return `<span class="badge text-bg-${cls}">${escapeHtml(priority || "-")}</span>`;
  }

  /**
   * 키보드 네비게이션 지원 함수들
   */
  
  /**
   * 키보드 이벤트 핸들러 설정
   * @param {HTMLElement} element - 이벤트를 설정할 요소
   * @param {Function} callback - 엔터/스페이스 키 눌렀을 때 실행할 함수
   */
  function setupKeyboardNavigation(element, callback) {
    if (!element || typeof callback !== 'function') return;
    
    element.addEventListener('keydown', function(e) {
      // 엔터 키 또는 스페이스 키
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        callback(e);
      }
    });
    
    // 포커스 가능하도록 tabindex 설정
    if (!element.hasAttribute('tabindex')) {
      element.setAttribute('tabindex', '0');
    }
  }
  
  /**
   * 모달 키보드 트랩 설정
   * @param {HTMLElement} modal - 모달 요소
   */
  function setupModalKeyboardTrap(modal) {
    if (!modal) return;
    
    const focusableElements = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    
    if (focusableElements.length === 0) return;
    
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    
    modal.addEventListener('keydown', function(e) {
      if (e.key === 'Tab') {
        if (e.shiftKey) {
          // Shift + Tab
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          // Tab
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
      
      // ESC 키로 모달 닫기
      if (e.key === 'Escape') {
        const closeButton = modal.querySelector('[data-bs-dismiss="modal"]');
        if (closeButton) {
          closeButton.click();
        }
      }
    });
    
    // 모달이 열릴 때 첫 번째 요소에 포커스
    modal.addEventListener('shown.bs.modal', function() {
      firstElement.focus();
    });
  }
  
  /**
   * 테이블 행 키보드 네비게이션 설정
   * @param {HTMLElement} table - 테이블 요소
   */
  function setupTableKeyboardNavigation(table) {
    if (!table) return;
    
    const rows = table.querySelectorAll('tbody tr');
    
    rows.forEach((row, index) => {
      row.setAttribute('tabindex', '0');
      row.setAttribute('role', 'button');
      
      row.addEventListener('keydown', function(e) {
        switch(e.key) {
          case 'ArrowDown':
            e.preventDefault();
            if (index < rows.length - 1) {
              rows[index + 1].focus();
            }
            break;
          case 'ArrowUp':
            e.preventDefault();
            if (index > 0) {
              rows[index - 1].focus();
            }
            break;
          case 'Enter':
          case ' ':
            e.preventDefault();
            // 행 클릭 이벤트 트리거
            row.click();
            break;
        }
      });
    });
  }
  
  /**
   * 스크린 리더를 위한 라이브 리전 업데이트
   * @param {string} message - 알림 메시지
   * @param {string} priority - 우선순위 ('polite' 또는 'assertive')
   */
  function announceToScreenReader(message, priority = 'polite') {
    let liveRegion = document.getElementById('sr-live-region');
    
    if (!liveRegion) {
      liveRegion = document.createElement('div');
      liveRegion.id = 'sr-live-region';
      liveRegion.className = 'sr-only';
      liveRegion.setAttribute('aria-live', priority);
      liveRegion.setAttribute('aria-atomic', 'true');
      document.body.appendChild(liveRegion);
    }
    
    liveRegion.textContent = message;
    
    // 메시지를 지우기 위해 잠시 후 초기화
    setTimeout(() => {
      liveRegion.textContent = '';
    }, 1000);
  }
  
  /**
   * 폼 유효성 검사 접근성 개선
   * @param {HTMLFormElement} form - 폼 요소
   */
  function enhanceFormAccessibility(form) {
    if (!form) return;
    
    const inputs = form.querySelectorAll('input, select, textarea');
    
    inputs.forEach(input => {
      // 에러 메시지 컨테이너 생성
      let errorContainer = input.parentNode.querySelector('.error-message');
      if (!errorContainer) {
        errorContainer = document.createElement('div');
        errorContainer.className = 'error-message text-danger small mt-1';
        errorContainer.setAttribute('role', 'alert');
        errorContainer.style.display = 'none';
        input.parentNode.appendChild(errorContainer);
      }
      
      // aria-describedby 설정
      const describedBy = input.getAttribute('aria-describedby') || '';
      if (!describedBy.includes(errorContainer.id)) {
        errorContainer.id = errorContainer.id || `error-${input.id || Math.random().toString(36).substr(2, 9)}`;
        input.setAttribute('aria-describedby', `${describedBy} ${errorContainer.id}`.trim());
      }
      
      // 실시간 유효성 검사
      input.addEventListener('blur', function() {
        validateInput(input, errorContainer);
      });
      
      input.addEventListener('input', function() {
        if (input.classList.contains('is-invalid')) {
          validateInput(input, errorContainer);
        }
      });
    });
  }
  
  /**
   * 개별 입력 필드 유효성 검사
   * @param {HTMLInputElement} input - 입력 필드
   * @param {HTMLElement} errorContainer - 에러 메시지 컨테이너
   */
  function validateInput(input, errorContainer) {
    const isValid = input.checkValidity();
    
    if (isValid) {
      input.classList.remove('is-invalid');
      input.classList.add('is-valid');
      errorContainer.style.display = 'none';
      input.setAttribute('aria-invalid', 'false');
    } else {
      input.classList.remove('is-valid');
      input.classList.add('is-invalid');
      errorContainer.textContent = input.validationMessage;
      errorContainer.style.display = 'block';
      input.setAttribute('aria-invalid', 'true');
      
      // 스크린 리더에 에러 알림
      announceToScreenReader(`${input.labels[0]?.textContent || '필드'}: ${input.validationMessage}`, 'assertive');
    }
  }

  // 공개 API
  window.DatabaseUtils = {
    // DB 관련 유틸리티
    getDbTypeIcon: getDbTypeIcon,
    getDbTypeBadge: getDbTypeBadge,
    getEnvironmentBadge: getEnvironmentBadge,
    getDefaultPort: getDefaultPort,
    getScheduleText: getScheduleText,
    getStatusBadge: getStatusBadge,
    getPriorityBadge: getPriorityBadge,
    
    // HTML 유틸리티
    escapeHtml: escapeHtml,
    
    // 알림 유틸리티
    showSuccess: showSuccess,
    showError: showError,
    showInfo: showInfo,
    showWarning: showWarning,
    showToast: showToast,
    showConfirm: showConfirm,
    
    // 접근성 유틸리티
    setupKeyboardNavigation: setupKeyboardNavigation,
    setupModalKeyboardTrap: setupModalKeyboardTrap,
    setupTableKeyboardNavigation: setupTableKeyboardNavigation,
    announceToScreenReader: announceToScreenReader,
    enhanceFormAccessibility: enhanceFormAccessibility
  };

})(window);
