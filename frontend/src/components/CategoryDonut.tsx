import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer } from "recharts";
import { cssVar, CATEGORICAL_SLOTS } from "../palette";
import TableView from "./TableView";

interface Row {
  name: string;
  clicks: number;
}

interface Props {
  title: string;
  rows: Row[];
  colorFor: (row: Row, index: number) => string;
}

export default function CategoryDonut({ title, rows, colorFor }: Props) {
  const grid = cssVar("--grid");
  const surface = cssVar("--surface-1");
  const text = cssVar("--text-primary");
  const secondary = cssVar("--text-secondary");

  return (
    <div className="card">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie data={rows} dataKey="clicks" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={2}>
            {rows.map((row, i) => (
              <Cell key={row.name} fill={colorFor(row, i)} stroke={surface} strokeWidth={2} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ background: surface, border: `1px solid ${grid}`, color: text }} />
          <Legend wrapperStyle={{ color: secondary, fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
      <TableView columns={["Name", "Clicks"]} rows={rows.map((r) => [r.name, r.clicks])} />
    </div>
  );
}

export function deviceColor(row: Row): string {
  const map: Record<string, string> = { desktop: "--series-1", mobile: "--series-2", tablet: "--series-3", bot: "--series-4" };
  return cssVar(map[row.name] ?? "--series-4");
}

export function slotColor(_row: Row, index: number): string {
  return cssVar(CATEGORICAL_SLOTS[index % CATEGORICAL_SLOTS.length]);
}
