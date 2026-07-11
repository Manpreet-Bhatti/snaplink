import { useEffect, useState } from "react";
import {
  clearToken,
  fetchAnalytics,
  fetchLinks,
  getToken,
  type Analytics,
  type LinkSummary,
  type Range,
} from "./api";
import StatTile from "./components/StatTile";
import ClicksOverTime from "./components/ClicksOverTime";
import TopReferrers from "./components/TopReferrers";
import Geography from "./components/Geography";
import CategoryDonut, { deviceColor, slotColor } from "./components/CategoryDonut";
import AuthForm from "./components/AuthForm";
import LinksPanel from "./components/LinksPanel";

const RANGES: { value: Range; label: string }[] = [
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "all", label: "All time" },
];

function App() {
  const [token, setToken] = useState<string | null>(() => getToken());
  const [links, setLinks] = useState<LinkSummary[]>([]);
  const [shortCode, setShortCode] = useState("");
  const [range, setRange] = useState<Range>("7d");
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  function refreshLinks() {
    fetchLinks()
      .then((ls) => {
        setLinks(ls);
        setShortCode((prev) => (ls.some((l) => l.short_code === prev) ? prev : (ls[0]?.short_code ?? "")));
      })
      .catch(() => setToken(null));
  }

  useEffect(() => {
    if (token) refreshLinks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!shortCode) {
      setAnalytics(null);
      return;
    }
    fetchAnalytics(shortCode, range)
      .then(setAnalytics)
      .catch(() => setToken(null));
  }, [shortCode, range]);

  if (!token) {
    return <AuthForm onAuth={setToken} />;
  }

  function logout() {
    clearToken();
    setToken(null);
  }

  return (
    <>
      <header>
        <h1>SnapLink Analytics</h1>
        {links.length > 0 && (
          <>
            <select value={shortCode} onChange={(e) => setShortCode(e.target.value)}>
              {links.map((l) => (
                <option key={l.short_code} value={l.short_code}>
                  {l.short_code} — {l.target_url}
                </option>
              ))}
            </select>
            <select value={range} onChange={(e) => setRange(e.target.value as Range)}>
              {RANGES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <img className="qr" src={`/api/links/${shortCode}/qr`} alt="QR code" width={80} height={80} />
          </>
        )}
        <button type="button" className="link-btn" onClick={logout} style={{ marginLeft: "auto" }}>
          Log out
        </button>
      </header>
      <main>
        <LinksPanel links={links} onChange={refreshLinks} />
        {links.length > 0 && analytics && (
          <>
            <div className="tiles">
              <StatTile label="Total clicks" value={analytics.total_clicks} />
              <StatTile label="Unique visitors" value={analytics.unique_visitors} />
              <StatTile label="Peak day" value={analytics.peak_day ?? "–"} />
            </div>
            <div className="charts">
              <ClicksOverTime series={analytics.series} />
              <TopReferrers referrers={analytics.referrers} />
              <Geography countries={analytics.countries} />
              <CategoryDonut
                title="Devices"
                rows={analytics.devices.map((d) => ({ name: d.device_type, clicks: d.clicks }))}
                colorFor={deviceColor}
              />
              <CategoryDonut
                title="Browsers"
                rows={analytics.browsers.map((b) => ({ name: b.browser, clicks: b.clicks }))}
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
