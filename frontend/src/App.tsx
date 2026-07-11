import { useEffect, useState } from "react";
import {
  fetchAnalytics,
  fetchLinks,
  type Analytics,
  type LinkSummary,
  type Range,
} from "./api";
import StatTile from "./components/StatTile";
import ClicksOverTime from "./components/ClicksOverTime";
import TopReferrers from "./components/TopReferrers";
import Geography from "./components/Geography";
import CategoryDonut, {
  deviceColor,
  slotColor,
} from "./components/CategoryDonut";

const RANGES: { value: Range; label: string }[] = [
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "all", label: "All time" },
];

function App() {
  const [links, setLinks] = useState<LinkSummary[]>([]);
  const [shortCode, setShortCode] = useState("");
  const [range, setRange] = useState<Range>("7d");
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  useEffect(() => {
    fetchLinks().then((ls) => {
      setLinks(ls);
      if (ls.length > 0) setShortCode(ls[0].short_code);
    });
  }, []);

  useEffect(() => {
    if (!shortCode) return;
    fetchAnalytics(shortCode, range).then(setAnalytics);
  }, [shortCode, range]);

  return (
    <>
      <header>
        <h1>SnapLink Analytics</h1>
        {links.length > 0 && (
          <>
            <select
              value={shortCode}
              onChange={(e) => setShortCode(e.target.value)}
            >
              {links.map((l) => (
                <option key={l.short_code} value={l.short_code}>
                  {l.short_code} — {l.target_url}
                </option>
              ))}
            </select>
            <select
              value={range}
              onChange={(e) => setRange(e.target.value as Range)}
            >
              {RANGES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <img
              className="qr"
              src={`/api/links/${shortCode}/qr`}
              alt="QR code"
              width={80}
              height={80}
            />
          </>
        )}
      </header>
      <main>
        {links.length === 0 && (
          <p className="empty">No links yet. Create one via POST /api/links.</p>
        )}
        {links.length > 0 && analytics && (
          <>
            <div className="tiles">
              <StatTile label="Total clicks" value={analytics.total_clicks} />
              <StatTile
                label="Unique visitors"
                value={analytics.unique_visitors}
              />
              <StatTile label="Peak day" value={analytics.peak_day ?? "–"} />
            </div>
            <div className="charts">
              <ClicksOverTime series={analytics.series} />
              <TopReferrers referrers={analytics.referrers} />
              <Geography countries={analytics.countries} />
              <CategoryDonut
                title="Devices"
                rows={analytics.devices.map((d) => ({
                  name: d.device_type,
                  clicks: d.clicks,
                }))}
                colorFor={deviceColor}
              />
              <CategoryDonut
                title="Browsers"
                rows={analytics.browsers.map((b) => ({
                  name: b.browser,
                  clicks: b.clicks,
                }))}
                colorFor={slotColor}
              />
            </div>
          </>
        )}
      </main>
    </>
  );
}

export default App;
