export interface Env {
  STATE_KV: KVNamespace;
  WORKER_TOKEN: string;
  ONESIGNAL_APP_ID?: string;
  ONESIGNAL_REST_API_KEY?: string;
}

type Months = Record<string, Record<string, number>>;

interface Snapshot {
  ts: string;
  months: Months;
  today: { date: string; vacant: number };
  meta?: Record<string, string>;
}

interface State {
  prev: Snapshot | null;
  curr: Snapshot | null;
  last_state: "normal" | "low";
  last_notify: { low?: string; spike?: string };
  flags: { is_low: boolean; is_spike: boolean };
}

const STATE_KEY = "innto:state";
const LOW_THRESHOLD = 10;
const NORMAL_THRESHOLD = 12;
const SPIKE_DELTA = 6;
const MAX_MINUTES = 70;
const SPIKE_COOLDOWN_MINUTES = 30;

const json = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body, null, 2), {
    ...init,
    headers: { "content-type": "application/json; charset=utf-8", ...(init.headers || {}) },
  });

async function loadState(env: Env): Promise<State> {
  const raw = await env.STATE_KV.get(STATE_KEY);
  if (!raw) {
    return {
      prev: null,
      curr: null,
      last_state: "normal",
      last_notify: {},
      flags: { is_low: false, is_spike: false },
    };
  }
  return JSON.parse(raw) as State;
}

async function saveState(env: Env, state: State): Promise<void> {
  await env.STATE_KV.put(STATE_KEY, JSON.stringify(state));
}

function isAuthorized(req: Request, token: string): boolean {
  const auth = req.headers.get("authorization") || "";
  return auth === `Bearer ${token}`;
}

function parseIsoMinutes(iso: string): number {
  return Math.floor(new Date(iso).getTime() / (1000 * 60));
}

function shouldSpikeNotify(curr: Snapshot, prev: Snapshot | null, lastSpike?: string): boolean {
  if (!prev) return false;
  const delta = Math.abs(curr.today.vacant - prev.today.vacant);
  if (delta < SPIKE_DELTA) return false;

  const minutes = parseIsoMinutes(curr.ts) - parseIsoMinutes(prev.ts);
  if (minutes > MAX_MINUTES || minutes < 0) return false;

  if (lastSpike) {
    const sinceLast = parseIsoMinutes(curr.ts) - parseIsoMinutes(lastSpike);
    if (sinceLast < SPIKE_COOLDOWN_MINUTES) return false;
  }
  return true;
}

async function sendOneSignal(env: Env, heading: string, content: string): Promise<void> {
  if (!env.ONESIGNAL_APP_ID || !env.ONESIGNAL_REST_API_KEY) return;

  const res = await fetch("https://onesignal.com/api/v1/notifications", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Basic ${env.ONESIGNAL_REST_API_KEY}`,
    },
    body: JSON.stringify({
      app_id: env.ONESIGNAL_APP_ID,
      included_segments: ["Subscribed Users"],
      headings: { en: heading, ja: heading },
      contents: { en: content, ja: content },
    }),
  });
  if (!res.ok) {
    console.warn("OneSignal failed", res.status, await res.text());
  }
}

async function evaluateAlerts(env: Env, state: State, curr: Snapshot): Promise<State> {
  const prev = state.curr;
  const next: State = {
    prev,
    curr,
    last_state: state.last_state,
    last_notify: { ...state.last_notify },
    flags: { is_low: false, is_spike: false },
  };

  if (curr.today.vacant <= LOW_THRESHOLD && state.last_state !== "low") {
    next.flags.is_low = true;
    next.last_state = "low";
    next.last_notify.low = curr.ts;
    await sendOneSignal(env, "低在庫アラート", `本日の空室が ${curr.today.vacant} 室です。`);
  } else if (curr.today.vacant >= NORMAL_THRESHOLD && state.last_state === "low") {
    next.last_state = "normal";
  }

  if (shouldSpikeNotify(curr, prev, state.last_notify.spike)) {
    next.flags.is_spike = true;
    next.last_notify.spike = curr.ts;
    const before = prev?.today.vacant;
    await sendOneSignal(
      env,
      "空室急変アラート",
      `本日の空室が ${before}→${curr.today.vacant} に変化しました。`,
    );
  }

  return next;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);

    if (req.method === "GET" && url.pathname === "/state") {
      const state = await loadState(env);
      return json(state);
    }

    if (req.method === "POST" && url.pathname === "/ingest") {
      if (!isAuthorized(req, env.WORKER_TOKEN)) {
        return json({ error: "unauthorized" }, { status: 401 });
      }
      const payload = (await req.json()) as Snapshot;
      const state = await loadState(env);
      const nextState = await evaluateAlerts(env, state, payload);
      await saveState(env, nextState);
      return json({ ok: true, state: nextState });
    }

    return json({ error: "not_found" }, { status: 404 });
  },
};
