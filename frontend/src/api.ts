export interface LinkSummary {
  short_code: string;
  target_url: string;
  click_count: number;
  created_at: string;
  is_active: boolean;
}

export interface Analytics {
  total_clicks: number;
  unique_visitors: number;
  peak_day: string | null;
  series: { date: string; clicks: number }[];
  referrers: { referrer: string; clicks: number }[];
  devices: { device_type: string; clicks: number }[];
  browsers: { browser: string; clicks: number }[];
  countries: { country_code: string; clicks: number }[];
}

export interface AuthResponse {
  token: string;
  user: { id: string; email: string };
}

export type Range = "24h" | "7d" | "30d" | "all";

const TOKEN_KEY = "snaplink_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(path, {
    ...init,
    headers: { ...authHeaders(), ...init.headers },
  });
  if (res.status === 401) clearToken();
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${init.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }
  return res;
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(`register failed: ${res.status}`);
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status}`);
  return res.json();
}

export async function fetchLinks(): Promise<LinkSummary[]> {
  const res = await apiFetch("/api/links");
  return res.json();
}

export async function fetchAnalytics(shortCode: string, range: Range): Promise<Analytics> {
  const res = await apiFetch(
    `/api/links/${encodeURIComponent(shortCode)}/analytics?range=${range}`,
  );
  return res.json();
}

export interface CreateLinkBody {
  target_url: string;
  custom_slug?: string;
  expires_at?: string;
  max_clicks?: number;
}

export async function createLink(body: CreateLinkBody): Promise<void> {
  await apiFetch("/api/links", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateLink(
  shortCode: string,
  body: { is_active?: boolean; expires_at?: string | null },
): Promise<void> {
  await apiFetch(`/api/links/${encodeURIComponent(shortCode)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteLink(shortCode: string): Promise<void> {
  await apiFetch(`/api/links/${encodeURIComponent(shortCode)}`, { method: "DELETE" });
}
