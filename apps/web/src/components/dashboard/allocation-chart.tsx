"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

// Categorical palette drawn from the design tokens' hue family so charts
// stay in the same visual system as the rest of the dashboard.
const COLORS = [
  "hsl(221 83% 53%)",
  "hsl(142 71% 40%)",
  "hsl(38 92% 50%)",
  "hsl(280 65% 55%)",
  "hsl(0 72% 51%)",
  "hsl(190 70% 45%)",
];

interface AllocationChartProps {
  title: string;
  data: Record<string, number>;
}

export function AllocationChart({ title, data }: AllocationChartProps) {
  const chartData = Object.entries(data)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  if (chartData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <p className="text-sm text-muted-foreground">No allocation data yet.</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <div className="flex items-center gap-4">
        <div className="h-40 w-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70} paddingAngle={2}>
                {chartData.map((entry, index) => (
                  <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="flex-1 space-y-1.5 text-sm">
          {chartData.map((entry, index) => (
            <li key={entry.name} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 truncate">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  aria-hidden
                />
                <span className="truncate text-muted-foreground">{entry.name}</span>
              </span>
              <span className="tabular-nums font-medium">{entry.value.toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
