/** Wire types - mirror of the Pydantic models in `horolog/api.py`.
 *
 *  Hand-written for now. Once the API is stable these should be generated from
 *  its OpenAPI schema (`openapi-typescript`) so the two cannot drift; until
 *  then this file is the seam to check when an endpoint changes.
 */

export type IntentKind = "task" | "habit" | "focus" | "buffer" | "meeting";
export type Priority = 1 | 2 | 3 | 4;

export interface Block {
  intent_id: string;
  title: string;
  kind: IntentKind;
  priority: Priority;
  occurrence: number;
  chunk: number;
  start: string;
  end: string;
  moved_from: string | null;
}

export interface Unmet {
  intent_id: string;
  title: string;
  priority: Priority;
  shortfall_minutes: number;
}

export interface Busy {
  label: string;
  start: string;
  end: string;
  source: string;
}

export interface Plan {
  blocks: Block[];
  unmet: Unmet[];
  busy: Busy[];
  solve_ms: number;
  complete: boolean;
  generated_at: string;
  origin: string;
  horizon_days: number;
}

export interface Intent {
  id: string;
  title: string;
  kind: IntentKind;
  priority: Priority;
  minutes_per_period: number;
  period_days: number | null;
  min_chunk_minutes: number;
  max_chunk_minutes: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    // The API puts a human-readable reason in `detail` for every 4xx it raises
    // deliberately - surface that rather than a bare status code.
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* non-JSON error body; keep the status line */
    }
    throw new Error(detail);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const api = {
  plan: () => request<Plan>("/api/plan"),
  resolve: () => request<Plan>("/api/plan/solve", { method: "POST" }),
  intents: () => request<Intent[]>("/api/intents"),
  remove: (id: string) => request<void>(`/api/intents/${id}`, { method: "DELETE" }),
  capture: (text: string) =>
    request<{ intent: Intent }>("/api/capture", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  setBusy: (events: Omit<Busy, "source">[]) =>
    request<{ events: number; blocks: number }>("/api/busy", {
      method: "PUT",
      body: JSON.stringify(events),
    }),
};

export function minutesBetween(start: string, end: string): number {
  return Math.round((Date.parse(end) - Date.parse(start)) / 60000);
}

export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

// --------------------------------------------------------------- analytics

export interface Slice {
  label: string;
  minutes: number;
  share: number;
}

export interface DayLoad {
  day: number;
  scheduled_minutes: number;
  meeting_minutes: number;
  longest_free_run_minutes: number;
}

export interface Analytics {
  horizon_days: number;
  window_minutes_per_day: number;
  focus_minutes: number;
  meeting_minutes: number;
  scheduled_minutes: number;
  unmet_minutes: number;
  meeting_load: number;
  fragmentation: number;
  longest_focus_run_minutes: number;
  after_hours_minutes: number;
  by_kind: Slice[];
  by_priority: Slice[];
  days: DayLoad[];
}

export const analytics = {
  get: () => request<Analytics>("/api/analytics"),
};

export const sync = {
  ics: (url: string) =>
    request<{ events: number; blocks: number }>("/api/sync/ics", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  caldav: (url: string, username: string, password: string) =>
    request<{ events: number; blocks: number }>("/api/sync/caldav", {
      method: "POST",
      body: JSON.stringify({ url, username, password }),
    }),
};

export const createIntent = (body: Record<string, unknown>) =>
  request<Intent>("/api/intents", { method: "POST", body: JSON.stringify(body) });

export const KIND_ORDER: IntentKind[] = ["focus", "task", "habit", "meeting", "buffer"];

export const PRIORITY_NAME: Record<Priority, string> = {
  1: "Critical",
  2: "High",
  3: "Normal",
  4: "Low",
};

/** Accent tint per priority - one hue, four weights. Shared by every view so
 *  the same block reads the same way on the grid, in the inbox, and in a chart. */
export const PRIORITY_TINT: Record<Priority, string> = {
  1: "color-mix(in srgb, var(--color-accent) 100%, transparent)",
  2: "color-mix(in srgb, var(--color-accent) 62%, transparent)",
  3: "color-mix(in srgb, var(--color-accent) 38%, transparent)",
  4: "color-mix(in srgb, var(--color-accent) 20%, transparent)",
};
