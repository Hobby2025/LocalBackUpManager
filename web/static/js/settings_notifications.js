// 알림 설정 페이지 스크립트 (CRLF)
(function () {
  "use strict";

  const form = document.getElementById("notif-settings");
  const elEnable = document.getElementById("enable");
  const elChEmail = document.getElementById("ch-email");
  const elChSlack = document.getElementById("ch-slack");
  const elChDiscord = document.getElementById("ch-discord");
  const elSmtpHost = document.getElementById("smtp_host");
  const elSmtpPort = document.getElementById("smtp_port");
  const elUseTls = document.getElementById("use_tls");
  const elUsername = document.getElementById("username");
  const elPassword = document.getElementById("password");
  const elFrom = document.getElementById("from_address");
  const elTo = document.getElementById("to_addresses");
  const elSlackHook = document.getElementById("slack_webhook_url");
  const elDiscordHook = document.getElementById("discord_webhook_url");
  const elSaveResult = document.getElementById("save-result");

  function setText(el, t) {
    if (el) el.textContent = t;
  }

  async function loadSettings() {
    try {
      const res = await fetch('/api/notifications/settings/');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "설정 조회 실패");
      const n = data.notifications || {};
      const ch = n.channels || {};
      elEnable.checked = !!n.enable;
      elChEmail.checked = !!ch.email;
      elChSlack.checked = !!ch.slack;
      elChDiscord.checked = !!ch.discord;
      const em = n.email || {};
      elSmtpHost.value = em.smtp_host || "";
      elSmtpPort.value = em.smtp_port != null ? em.smtp_port : 587;
      elUseTls.checked = !!em.use_tls;
      elUsername.value = em.username || "";
      elPassword.value = em.password || "";
      elFrom.value = em.from_address || "";
      elTo.value = (em.to_addresses || []).join(",");
      const sk = n.slack || {};
      elSlackHook.value = sk.webhook_url || "";
      const dc = n.discord || {};
      elDiscordHook.value = dc.webhook_url || "";
    } catch (e) {
      console.error(e);
      setText(elSaveResult, e.message || "설정 조회 실패");
    }
  }

  function parseToAddresses(raw) {
    return (raw || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  form &&
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      try {
        const payload = {
          notifications: {
            enable: elEnable.checked,
            channels: {
              email: elChEmail.checked,
              slack: elChSlack.checked,
              discord: elChDiscord.checked,
            },
            email: {
              smtp_host: elSmtpHost.value.trim(),
              smtp_port: Number(elSmtpPort.value) || 587,
              use_tls: elUseTls.checked,
              username: elUsername.value.trim(),
              password: elPassword.value,
              from_address: elFrom.value.trim(),
              to_addresses: parseToAddresses(elTo.value),
            },
            slack: { webhook_url: elSlackHook.value.trim() },
            discord: { webhook_url: elDiscordHook.value.trim() },
          },
        };
        const res = await fetch('/api/notifications/settings/', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "설정 저장 실패");
        setText(elSaveResult, "저장 완료");
      } catch (e) {
        console.error(e);
        setText(elSaveResult, e.message || "저장 실패");
      }
    });

  document.addEventListener("DOMContentLoaded", loadSettings);
})();
