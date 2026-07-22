import { useState } from "react";
import { createLink, deleteLink, updateLink, type LinkSummary } from "../api";

export default function LinksPanel({
  links,
  onChange,
}: {
  links: LinkSummary[];
  onChange: () => void;
}) {
  const [targetUrl, setTargetUrl] = useState("");
  const [customSlug, setCustomSlug] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [maxClicks, setMaxClicks] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createLink({
        target_url: targetUrl,
        custom_slug: customSlug || undefined,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : undefined,
        max_clicks: maxClicks ? Number(maxClicks) : undefined,
      });
      setTargetUrl("");
      setCustomSlug("");
      setExpiresAt("");
      setMaxClicks("");
      onChange();
    } catch {
      setError("Could not create link (invalid URL, or slug taken/reserved?)");
    }
  }

  async function toggleActive(link: LinkSummary) {
    await updateLink(link.short_code, { is_active: !link.is_active });
    onChange();
  }

  async function remove(link: LinkSummary) {
    if (!window.confirm(`Delete ${link.short_code}? This can't be undone.`))
      return;
    await deleteLink(link.short_code);
    onChange();
  }

  return (
    <div className="card card-full">
      <h2>Your links</h2>
      <form className="form-row" onSubmit={handleCreate}>
        <input
          type="url"
          placeholder="https://example.com/long/path"
          value={targetUrl}
          onChange={(e) => setTargetUrl(e.target.value)}
          required
        />
        <input
          placeholder="custom slug (optional)"
          value={customSlug}
          onChange={(e) => setCustomSlug(e.target.value)}
        />
        <input
          type="date"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
          title="expires at (optional)"
        />
        <input
          type="number"
          min={1}
          placeholder="max clicks"
          value={maxClicks}
          onChange={(e) => setMaxClicks(e.target.value)}
        />
        <button type="submit">Shorten</button>
      </form>
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>Code</th>
            <th>Target</th>
            <th>Clicks</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {links.map((l) => (
            <tr key={l.short_code}>
              <td>{l.short_code}</td>
              <td className="truncate">{l.target_url}</td>
              <td>{l.click_count}</td>
              <td>{l.is_active ? "active" : "disabled"}</td>
              <td className="link-row-actions">
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => toggleActive(l)}
                >
                  {l.is_active ? "Disable" : "Enable"}
                </button>
                <button
                  type="button"
                  className="link-btn danger"
                  onClick={() => remove(l)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {links.length === 0 && (
            <tr>
              <td colSpan={5} className="empty">
                No links yet — create one above.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
