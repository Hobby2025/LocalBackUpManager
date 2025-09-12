// 알림 이력 / 테스트 페이지 스크립트 (CRLF)
(function () {
  "use strict";

  const elForm = document.getElementById("test-form");
  const elChannel = document.getElementById("test-channel");
  const elTitle = document.getElementById("test-title");
  const elMessage = document.getElementById("test-message");
  const elTo = document.getElementById("test-to");
  const elResult = document.getElementById("test-result");

  const elFltForm = document.getElementById("flt-form");
  const elFltLevel = document.getElementById("flt-level");
  const elFltStatus = document.getElementById("flt-status");
  const elNotifBody = document.getElementById("notif-body");
  const btnBroadcast = document.getElementById("btn-broadcast");

  function setText(el, txt) {
    if (el) el.textContent = txt;
  }

  // 상세 모달 관련 요소 참조
  let notifDetailModal;
  document.addEventListener("DOMContentLoaded", function () {
    const el = document.getElementById("notifDetailModal");
    if (el && window.bootstrap) {
      notifDetailModal = new bootstrap.Modal(el);
    }
  });

  // 목록에서 상세/재전송 동작 처리 (이벤트 위임)
  document.addEventListener("click", async function (e) {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const tr = btn.closest("tr[data-id]");
    if (!tr) return;
    const id = tr.getAttribute("data-id");
    const action = btn.getAttribute("data-action");
    if (action === "detail") {
      await openDetail(id);
      if (notifDetailModal) notifDetailModal.show();
      return;
    }
    if (action === "resend") {
      await resend(id);
      await listNotifications();
      return;
    }
  });

  // 상세 열기: GET /api/notifications/{id} 로드하여 모달에 표시
  async function openDetail(id) {
    try {
      const res = await fetch(`/api/notifications/${encodeURIComponent(id)}`);
      const n = await res.json();
      if (!res.ok) throw new Error(n.detail || "상세 조회 실패");
      setText(document.getElementById("nd-id"), n.id || "-");
      setText(document.getElementById("nd-type"), n.notification_type || "-");
      setText(document.getElementById("nd-level"), n.level || "-");
      setText(document.getElementById("nd-status"), n.status || "-");
      setText(document.getElementById("nd-db"), n.database_id || "-");
      setText(document.getElementById("nd-bk"), n.backup_id || "-");
      setText(document.getElementById("nd-rec"), n.recipient || "-");
      setText(document.getElementById("nd-title"), n.title || "-");
      const msgEl = document.getElementById("nd-msg");
      if (msgEl) msgEl.textContent = n.message || "-";
      setText(document.getElementById("nd-err"), n.error_message || "-");
      // 모달의 재전송 버튼에 현재 id 저장
      const btnResend = document.getElementById("btn-resend-modal");
      if (btnResend) {
        btnResend.setAttribute("data-id", n.id);
      }
    } catch (e) {
      console.error(e);
    }
  }

  // 재전송
  async function resend(id) {
    try {
      const res = await fetch(
        `/api/notifications/${encodeURIComponent(id)}/resend`,
        { method: "POST" }
      );
      const data = await res.json();
      // 간단 결과 출력
      const el = document.getElementById("test-result");
      if (el) {
        el.textContent = JSON.stringify(data);
      }
    } catch (e) {
      console.error(e);
    }
  }

  // 모달 내 재전송 버튼 클릭 처리
  document.addEventListener("click", async function (e) {
    const btn = e.target.closest("#btn-resend-modal");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (!id) return;
    await resend(id);
    await listNotifications();
  });

  async function listNotifications() {
    try {
      const params = new URLSearchParams();
      if (elFltLevel && elFltLevel.value) params.set("level", elFltLevel.value);
      if (elFltStatus && elFltStatus.value)
        params.set("status_filter", elFltStatus.value);
      const res = await fetch(`/api/notifications/?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "알림 이력 조회 실패");
      const items = data.notifications || [];
      if (items.length === 0) {
        elNotifBody.innerHTML =
          '<tr><td colspan="5" class="text-center text-muted">데이터 없음</td></tr>';
        return;
      }
      elNotifBody.innerHTML = items
        .map((n) => {
          const ts = n.created_at
            ? new Date(n.created_at).toLocaleString()
            : "-";
          return `<tr data-id="${n.id}">
          <td>${ts}</td>
          <td>${escapeHtml(n.notification_type)}</td>
          <td>${escapeHtml(n.level)}</td>
          <td>${escapeHtml(n.status)}</td>
          <td>${escapeHtml(n.title || "")}</td>
          <td class="text-end">
            <div class="btn-group btn-group-sm" role="group">
              <button class="btn btn-outline-secondary" data-action="detail">상세</button>
              <button class="btn btn-outline-primary" data-action="resend">재전송</button>
            </div>
          </td>
        </tr>`;
        })
        .join("");
    } catch (e) {
      console.error(e);
      elNotifBody.innerHTML =
        '<tr><td colspan="5" class="text-center text-danger">알림 이력 조회 실패</td></tr>';
    }
  }

  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  elFltForm &&
    elFltForm.addEventListener("submit", function (e) {
      e.preventDefault();
      listNotifications();
    });

  elForm &&
    elForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      try {
        const payload = {
          channel: elChannel.value.trim() || undefined,
          title: elTitle.value.trim() || "테스트 알림",
          message: elMessage.value.trim() || "테스트 메시지",
        };
        const toRaw = (elTo.value || "").trim();
        if (toRaw)
          payload.to = toRaw
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        const res = await fetch("/api/notifications/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        setText(elResult, JSON.stringify(data));
        await listNotifications();
      } catch (e) {
        console.error(e);
        setText(elResult, e.message || "전송 실패");
      }
    });

  btnBroadcast &&
    btnBroadcast.addEventListener("click", async function () {
      try {
        const payload = {
          title: elTitle.value.trim() || "알림",
          message: elMessage.value.trim() || "메시지",
        };
        const res = await fetch("/api/notifications/broadcast", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        setText(elResult, JSON.stringify(data));
        await listNotifications();
      } catch (e) {
        console.error(e);
        setText(elResult, e.message || "브로드캐스트 실패");
      }
    });

  document.addEventListener("DOMContentLoaded", listNotifications);
})();
