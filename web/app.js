const stateUrl = window.STATE_URL || "https://YOUR_WORKER_DOMAIN/state";

const tables = document.getElementById("tables");
const updatedAt = document.getElementById("updatedAt");

document.getElementById("refreshBtn").addEventListener("click", loadState);
document.getElementById("subscribeBtn").addEventListener("click", subscribePush);

function dayRows(monthKey, dayMap, todayDate) {
  return Object.entries(dayMap)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([day, vacant]) => {
      const date = `${monthKey}-${day}`;
      const isToday = date === todayDate;
      const low = vacant <= 10 ? `<span class="badge">低在庫(<=10)</span>` : "";
      return `<tr class="${isToday ? "today" : ""}"><td>${date}</td><td>${vacant}</td><td>${low}</td></tr>`;
    })
    .join("");
}

function render(state) {
  const curr = state.curr;
  if (!curr) {
    tables.innerHTML = "<p>データがまだありません。</p>";
    return;
  }
  updatedAt.textContent = `更新時刻: ${curr.ts}`;
  tables.innerHTML = Object.entries(curr.months)
    .map(([month, dayMap]) => {
      return `<article class="month"><h2>${month}</h2><table><thead><tr><th>日付</th><th>空室数</th><th>状態</th></tr></thead><tbody>${dayRows(month, dayMap, curr.today.date)}</tbody></table></article>`;
    })
    .join("");
}

async function loadState() {
  const res = await fetch(stateUrl, { cache: "no-store" });
  if (!res.ok) throw new Error(`failed: ${res.status}`);
  const data = await res.json();
  render(data);
}

async function subscribePush() {
  window.OneSignalDeferred = window.OneSignalDeferred || [];
  window.OneSignalDeferred.push(async function (OneSignal) {
    await OneSignal.init({
      appId: window.ONESIGNAL_APP_ID || "YOUR_ONESIGNAL_APP_ID",
      allowLocalhostAsSecureOrigin: true,
    });
    await OneSignal.Notifications.requestPermission();
  });
}

window.OneSignalDeferred = window.OneSignalDeferred || [];
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js");
}

loadState().catch((err) => {
  tables.innerHTML = `<p>取得失敗: ${err.message}</p>`;
});
