// پنل مدیریت MODASR — بدون فریم‌ورک، همه‌ی داده‌ها از /api/* واقعی می‌آیند.
// این فایل عمداً هیچ داده‌ی نمایشی/ساختگی ندارد؛ اگر API چیزی برنگرداند، پیام خطا یا
// "بدون داده" نشان داده می‌شود، نه عدد جعلی.

const PLATFORM_FA = { telegram: "تلگرام", bale: "بله", rubika: "روبیکا" };

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let data = {};
  try { data = await res.json(); } catch (_) { /* بدنه خالی */ }
  if (!res.ok) throw new Error(data.error || `خطای HTTP ${res.status}`);
  return data;
}

// ---------------- ورود / خروج ----------------
async function checkAuth() {
  const { authenticated } = await api("/api/me");
  showScreen(authenticated);
  if (authenticated) loadPage("dashboard");
}

function showScreen(authenticated) {
  document.getElementById("login-screen").hidden = authenticated;
  document.getElementById("app-screen").hidden = !authenticated;
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  errEl.hidden = true;
  try {
    await api("/api/login", { method: "POST", body: JSON.stringify({ password }) });
    document.getElementById("login-password").value = "";
    showScreen(true);
    loadPage("dashboard");
  } catch (err) {
    errEl.textContent = err.message;
    errEl.hidden = false;
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  showScreen(false);
});

// ---------------- ناوبری ----------------
document.querySelectorAll(".nav-btn[data-page]").forEach((btn) => {
  btn.addEventListener("click", () => loadPage(btn.dataset.page));
});

function loadPage(name) {
  document.querySelectorAll(".nav-btn[data-page]").forEach((b) => b.classList.toggle("active", b.dataset.page === name));
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === `page-${name}`));
  document.getElementById("sidebar").classList.remove("open");
  if (name === "dashboard") renderDashboard();
  else if (name === "users") renderUsers();
  else if (name === "settings") renderSettings();
}

document.getElementById("menu-toggle").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});

// ---------------- داشبورد ----------------
async function renderDashboard() {
  const cards = document.getElementById("dash-stats");
  cards.innerHTML = `<div class="card"><div class="label">در حال بارگذاری...</div></div>`;
  try {
    const d = await api("/api/dashboard");
    const platformsHtml = Object.entries(d.users_by_platform)
      .map(([p, n]) => `<div class="card"><div class="label">کاربران ${PLATFORM_FA[p] || p}</div><div class="value">${n}</div></div>`)
      .join("");
    cards.innerHTML = `
      <div class="card"><div class="label">کل کاربران</div><div class="value">${d.total_users}</div></div>
      ${platformsHtml || '<div class="card"><div class="label">کاربران به تفکیک پلتفرم</div><div class="value">—</div></div>'}
      <div class="card"><div class="label">کل پیام‌های مکالمه</div><div class="value">${d.total_conversation_messages}</div></div>
    `;
    const tbody = document.querySelector("#usage-table tbody");
    tbody.innerHTML = d.usage_today.length
      ? d.usage_today.map((u) => `<tr><td>${u.feature}</td><td>${u.distinct_users}</td><td>${u.total_calls}</td></tr>`).join("")
      : `<tr><td colspan="3" class="muted">امروز هنوز مصرفی ثبت نشده.</td></tr>`;
  } catch (err) {
    cards.innerHTML = `<div class="card"><div class="label error-text">خطا: ${err.message}</div></div>`;
  }
}

// ---------------- کاربران + اشتراک ----------------
let subscriptionPlans = null;

async function getPlans() {
  if (!subscriptionPlans) {
    const { plans } = await api("/api/subscriptions/plans");
    subscriptionPlans = plans;
  }
  return subscriptionPlans;
}

function subscriptionBadge(sub) {
  if (!sub) return `<span class="status-unknown">بدون اشتراک</span>`;
  if (sub.active_now) {
    const until = sub.expires_at ? new Date(sub.expires_at).toLocaleDateString("fa-IR") : "همیشگی";
    return `<span class="status-ok">فعال (${sub.plan}) تا ${until}</span>`;
  }
  return `<span class="status-bad">${sub.status === "revoked" ? "لغوشده" : "منقضی"} (${sub.plan})</span>`;
}

async function renderUsers() {
  const tbody = document.getElementById("users-table-body");
  tbody.innerHTML = `<tr><td colspan="7" class="muted">در حال بارگذاری...</td></tr>`;
  const platform = document.getElementById("users-platform-filter").value;
  try {
    const plans = await getPlans();
    const planOptions = Object.entries(plans)
      .map(([key, p]) => `<option value="${key}">${p.label}</option>`).join("");

    const qs = platform ? `?platform=${encodeURIComponent(platform)}` : "";
    const { users } = await api(`/api/users${qs}`);
    tbody.innerHTML = users.length
      ? users.map((u) => `
          <tr data-user-id="${u.id}">
            <td>${PLATFORM_FA[u.platform] || u.platform}</td>
            <td>${u.display_name || "—"}</td>
            <td>${u.platform_user_id}</td>
            <td>${u.messages_today}</td>
            <td>${new Date(u.created_at).toLocaleDateString("fa-IR")}</td>
            <td>${subscriptionBadge(u.subscription)}</td>
            <td class="sub-actions">
              <select class="sub-plan-select">${planOptions}</select>
              <button class="sub-grant-btn" data-user="${u.id}">صدور/تمدید</button>
              ${u.subscription && u.subscription.active_now
                ? `<button class="sub-revoke-btn" data-user="${u.id}">لغو</button>` : ""}
            </td>
          </tr>`).join("")
      : `<tr><td colspan="7" class="muted">کاربری یافت نشد.</td></tr>`;

    tbody.querySelectorAll(".sub-grant-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const row = btn.closest("tr");
        const plan = row.querySelector(".sub-plan-select").value;
        btn.disabled = true;
        try {
          await api(`/api/users/${btn.dataset.user}/subscription/grant`, {
            method: "POST", body: JSON.stringify({ plan, note: "صدور از پنل مدیریت" }),
          });
          renderUsers();
        } catch (err) {
          alert("خطا: " + err.message);
          btn.disabled = false;
        }
      });
    });
    tbody.querySelectorAll(".sub-revoke-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("اشتراک این کاربر لغو شود؟")) return;
        btn.disabled = true;
        try {
          await api(`/api/users/${btn.dataset.user}/subscription/revoke`, {
            method: "POST", body: JSON.stringify({ note: "لغو از پنل مدیریت" }),
          });
          renderUsers();
        } catch (err) {
          alert("خطا: " + err.message);
          btn.disabled = false;
        }
      });
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="error-text">خطا: ${err.message}</td></tr>`;
  }
}
document.getElementById("users-refresh").addEventListener("click", renderUsers);
document.getElementById("users-platform-filter").addEventListener("change", renderUsers);

// ---------------- تنظیمات / وضعیت ----------------
function statusBadge(target, cached) {
  if (!cached) return `<span class="status-unknown">بررسی نشده</span>`;
  if (cached.ok) return `<span class="status-ok">✅ متصل${cached.detail ? " — " + cached.detail : ""}</span>`;
  return `<span class="status-bad">❌ ${cached.error || "خطا"}</span>`;
}

async function renderSettings() {
  const cards = document.getElementById("settings-cards");
  cards.innerHTML = `<div class="card"><div class="label">در حال بارگذاری...</div></div>`;
  try {
    const [settings, health] = await Promise.all([api("/api/settings"), api("/api/health")]);
    cards.innerHTML = `
      <div class="card">
        <div class="label">OpenRouter</div>
        <div class="value" style="font-size:1rem">${settings.openrouter.model}</div>
        <div class="small muted">کلید: ${settings.openrouter.api_key_configured ? settings.openrouter.api_key_preview : "تنظیم نشده"}</div>
        <div id="health-openrouter">${statusBadge("openrouter", health.openrouter)}</div>
        <button data-check="openrouter">بررسی زنده</button>
      </div>
      <div class="card">
        <div class="label">تلگرام</div>
        <div class="small muted">توکن: ${settings.telegram.bot_token_configured ? settings.telegram.bot_token_preview : "تنظیم نشده"}</div>
        <div id="health-telegram">${statusBadge("telegram", health.telegram)}</div>
        <button data-check="telegram">بررسی زنده</button>
      </div>
      <div class="card">
        <div class="label">بله</div>
        <div class="small muted">توکن: ${settings.bale.bot_token_configured ? settings.bale.bot_token_preview : "تنظیم نشده"}</div>
        <div id="health-bale">${statusBadge("bale", health.bale)}</div>
        <button data-check="bale">بررسی زنده</button>
      </div>
      <div class="card">
        <div class="label">روبیکا</div>
        <div class="small muted">توکن: ${settings.rubika.bot_token_configured ? settings.rubika.bot_token_preview : "تنظیم نشده"}</div>
        <div class="small status-unknown">وضعیت: غیرفعال، در انتظار تأیید نهایی</div>
      </div>
    `;
    cards.querySelectorAll("button[data-check]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const target = btn.dataset.check;
        btn.disabled = true;
        btn.textContent = "در حال بررسی...";
        try {
          const result = await api(`/api/health/${target}`, { method: "POST" });
          document.getElementById(`health-${target}`).innerHTML = statusBadge(target, result);
        } catch (err) {
          document.getElementById(`health-${target}`).innerHTML = `<span class="status-bad">خطا: ${err.message}</span>`;
        }
        btn.disabled = false;
        btn.textContent = "بررسی زنده";
      });
    });
  } catch (err) {
    cards.innerHTML = `<div class="card"><div class="label error-text">خطا: ${err.message}</div></div>`;
  }
}

// ---------------- چت ----------------
let chatHistory = [];

function appendChatMessage(role, text) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;
  appendChatMessage("user", message);
  input.value = "";
  const model = document.getElementById("chat-model").value.trim() || undefined;
  try {
    const { reply } = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, model, history: chatHistory }),
    });
    appendChatMessage("assistant", reply);
    chatHistory.push({ role: "user", content: message }, { role: "assistant", content: reply });
    chatHistory = chatHistory.slice(-16);
  } catch (err) {
    appendChatMessage("error", `خطا: ${err.message}`);
  }
});

document.getElementById("chat-clear").addEventListener("click", () => {
  chatHistory = [];
  document.getElementById("chat-log").innerHTML = "";
});

checkAuth();
