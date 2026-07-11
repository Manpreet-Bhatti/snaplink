import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { cssVar } from "../palette";
import TableView from "./TableView";
import type { Analytics } from "../api";

export default function Geography({
  countries,
}: {
  countries: Analytics["countries"];
}) {
  const fill = cssVar("--series-2");
  const grid = cssVar("--grid");
  const muted = cssVar("--text-muted");
  const surface = cssVar("--surface-1");
  const text = cssVar("--text-primary");

  return (
    <div className="card card-full">
      <h2>Geography</h2>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={countries} layout="vertical" margin={{ left: 24 }}>
          <CartesianGrid stroke={grid} horizontal={false} />
          <XAxis
            type="number"
            allowDecimals={false}
            stroke={muted}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="country_code"
            stroke={muted}
            tick={{ fontSize: 12 }}
            width={100}
          />
          <Tooltip
            contentStyle={{
              background: surface,
              border: `1px solid ${grid}`,
              color: text,
            }}
          />
          <Bar dataKey="clicks" fill={fill} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <TableView
        columns={["Country", "Clicks"]}
        rows={countries.map((c) => [c.country_code, c.clicks])}
      />
    </div>
  );
}
