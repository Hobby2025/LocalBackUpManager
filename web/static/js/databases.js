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
  const formHost = document.getElementById("form-host");
  const formPort = document.getElementById("form-port");
  const formDatabaseName = document.getElementById("form-database_name");
  const formUsername = document.getElementById("form-username");
  const formPassword = document.getElementById("form-password");
  const formSslMode = document.getElementById("form-ssl_mode");
  const formEnvironment = document.getElementById("form-environment");
  const formPriority = document.getElementById("form-priority");
  const btnSave = document.getElementById("btn-save");

  // 필터 요소
  const fltQ = document.getElementById("flt-q");
  const fltEnv = document.getElementById("flt-env");
  const fltPriority = document.getElementById("flt-priority");
  const fltStatus = document.getElementById("flt-status");
  const fltIncludeInactive = document.getElementById("flt-include-inactive");
  const fltSort = document.getElementById("flt-sort");
  const fltOrder = document.getElementById("flt-order");
  const fltPageSize = document.getElementById("flt-page-size");

  // 페이징 상태
  let state = {
    page: 1,
    pageSize: Number(fltPageSize ? fltPageSize.value : 20) || 20,
    total: 0,
  };

  // 유틸: HTML 이스케이프
  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 유틸: SweetAlert2 토스트
  function swToast(message, icon = "success") {
    if (window.Swal) {
      const t = window.Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 2500,
        timerProgressBar: true,
      });
      t.fire({ icon: icon, title: message });
    } else {
      alert(message);
    }
  }

  // 유틸: SweetAlert2 확인
  function swConfirm(message) {
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
          '<tr><td colspan="8" class="text-center text-muted">데이터 없음</td></tr>';
        return;
      }
      tbody.innerHTML = items.map((it) => rowTemplate(it)).join("");
    } catch (e) {
      console.error(e);
      tbody.innerHTML =
        '<tr><td colspan="8" class="text-center text-danger">DB 목록 로드 실패</td></tr>';
      swToast(e.message || 'DB 목록 로드 실패', 'error');
    }
  }

  // 배지(상태/환경/우선순위) 일원화
  function statusBadge(status) {
    const s = (status || "").toLowerCase();
    const cls =
      s === "connected" ? "success" : s === "error" ? "danger" : "secondary";
    return `<span class="badge text-bg-${cls}">${escapeHtml(
      status || "알 수 없음"
    )}</span>`;
  }
  function envBadge(env) {
    const map = {
      production: "danger",
      staging: "warning",
      development: "info",
    };
    const cls = map[(env || "").toLowerCase()] || "secondary";
    return `<span class="badge text-bg-${cls}">${escapeHtml(
      env || "-"
    )}</span>`;
  }
  function priorityBadge(p) {
    const map = { high: "danger", medium: "primary", low: "secondary" };
    const cls = map[(p || "").toLowerCase()] || "secondary";
    return `<span class="badge text-bg-${cls}">${escapeHtml(p || "-")}</span>`;
  }

  function rowTemplate(it) {
    return `
      <tr>
        <td>${escapeHtml(it.name)}</td>
        <td>${escapeHtml(it.display_name)}</td>
        <td>${envBadge(it.environment)}</td>
        <td>${priorityBadge(it.priority)}</td>
        <td>${escapeHtml(it.host)}</td>
        <td>${escapeHtml(it.port)}</td>
        <td>${statusBadge(it.connection_status)}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm" role="group">
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
      formHost.value = it.host || "";
      formPort.value = it.port || 5432;
      formDatabaseName.value = it.database_name || "";
      formUsername.value = it.username || "";
      formPassword.value = ""; // 공란이면 비밀번호 유지
      formSslMode.value = it.ssl_mode || "require";
      formEnvironment.value = it.environment || "development";
      formPriority.value = it.priority || "medium";
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
        host: formHost.value.trim(),
        port: Number(formPort.value) || 5432,
        database_name: formDatabaseName.value.trim(),
        username: formUsername.value.trim(),
        // password는 신규 시 필수, 수정 시 공란이면 전송하지 않음
        ssl_mode: formSslMode.value.trim(),
        environment: formEnvironment.value,
        priority: formPriority.value,
      };

      if (
        !payload.name ||
        !payload.display_name ||
        !payload.host ||
        !payload.database_name ||
        !payload.username
      ) {
        swToast("필수 항목을 모두 입력하세요.", 'warning');
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

  document.addEventListener("DOMContentLoaded", loadList);
})();
