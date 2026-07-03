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
}

export type Range = "24h" | "7d" | "30d" | "all";

export async function fetchLinks(): Promise<LinkSummary[]> {
  const res = await fetch("/api/links");
  if (!res.ok) throw new Error(`GET /api/links failed: ${res.status}`);
  return res.json();
}

export async function fetchAnalytics(shortCode: string, range: Range): Promise<Analytics> {
  const res = await fetch(`/api/links/${encodeURIComponent(shortCode)}/analytics?range=${range}`);
  if (!res.ok) throw new Error(`GET analytics failed: ${res.status}`);
  return res.json();
}
