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
    showConfirm: showConfirm
  };

})(window);
