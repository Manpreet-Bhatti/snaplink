import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { cssVar } from "../palette";
import TableView from "./TableView";
import type { Analytics } from "../api";

export default function ClicksOverTime({ series }: { series: Analytics["series"] }) {
  const stroke = cssVar("--series-1");
  const grid = cssVar("--grid");
  const muted = cssVar("--text-muted");
  const surface = cssVar("--surface-1");
  const text = cssVar("--text-primary");

  return (
    <div className="card card-full">
      <h2>Clicks over time</h2>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={series}>
          <CartesianGrid stroke={grid} vertical={false} />
          <XAxis dataKey="date" stroke={muted} tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} stroke={muted} tick={{ fontSize: 12 }} />
          <Tooltip contentStyle={{ background: surface, border: `1px solid ${grid}`, color: text }} />
          <Line type="monotone" dataKey="clicks" stroke={stroke} strokeWidth={2} dot={series.length <= 40} />
        </LineChart>
      </ResponsiveContainer>
      <TableView columns={["Date", "Clicks"]} rows={series.map((s) => [s.date, s.clicks])} />
    </div>
  );
}
