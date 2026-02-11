const stateUrl = window.STATE_URL || "https://YOUR_WORKER_DOMAIN/state";

const calendars = document.getElementById("calendars");
const updatedAt = document.getElementById("updatedAt");

document.getElementById("refreshBtn").addEventListener("click", loadState);
document.getElementById("subscribeBtn").addEventListener("click", subscribePush);

const WEEK_LABELS = ["日", "月", "火", "水", "木", "金", "土"];

function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function monthToCells(monthKey, dayMap, todayDate) {
  const [yearStr, monthStr] = monthKey.split("-");
  const year = Number(yearStr);
  const month = Number(monthStr);
  const firstWeekday = new Date(year, month - 1, 1).getDay();
  const count = daysInMonth(year, month);

  const cells = [];
  for (let i = 0; i < firstWeekday; i += 1) {
    cells.push('<div class="day-cell empty"></div>');
  }

  for (let day = 1; day <= count; day += 1) {
    const dayStr = String(day).padStart(2, "0");
    const date = `${monthKey}-${dayStr}`;
    const vacant = dayMap?.[dayStr];
    const isToday = date === todayDate;
    const isLow = typeof vacant === "number" && vacant <= 10;

    cells.push(
      `<div class="day-cell ${isToday ? "today" : ""}">`
        + `<div class="day-head"><span class="day-number">${day}</span>${isLow ? '<span class="badge">低在庫</span>' : ""}</div>`
        + `<div class="vacant">${typeof vacant === "number" ? `空室: ${vacant}` : "-"}</div>`
      + "</div>",
    );
  }

  return cells.join("");
}

function render(state) {
  const curr = state.curr;
  if (!curr) {
    calendars.innerHTML = "<p>データがまだありません。</p>";
    return;
  }

  updatedAt.textContent = `更新時刻: ${curr.ts}`;

  const monthEntries = Object.entries(curr.months)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(0, 2);

  calendars.innerHTML = monthEntries
    .map(([monthKey, dayMap]) => {
      return `<article class="month-card">`
        + `<h2>${monthKey}</h2>`
        + `<div class="week-header">${WEEK_LABELS.map((w) => `<span>${w}</span>`).join("")}</div>`
        + `<div class="calendar-grid">${monthToCells(monthKey, dayMap, curr.today.date)}</div>`
        + `</article>`;
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
  calendars.innerHTML = `<p>取得失敗: ${err.message}</p>`;
});
