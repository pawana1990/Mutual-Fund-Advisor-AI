"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, scoreColorClass } from "@/lib/utils";
import type { HealthScore } from "@/types/api";
import { RadialBar, RadialBarChart } from "recharts";

const SUB_SCORE_LABELS: Record<string, string> = {
  diversification_score: "Diversification",
  risk_score: "Risk",
  returns_score: "Returns",
  fees_score: "Fees",
  fund_quality_score: "Fund Quality",
  tax_efficiency_score: "Tax Efficiency",
  asset_allocation_score: "Asset Allocation",
  goal_readiness_score: "Goal Readiness",
};

export function HealthScoreGauge({ score }: { score: HealthScore }) {
  const data = [{ name: "score", value: score.overall_score, fill: "hsl(var(--primary))" }];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio Health Score</CardTitle>
      </CardHeader>
      <div className="flex flex-col items-center gap-2 sm:flex-row sm:items-start sm:gap-6">
        <div className="relative h-40 w-40 shrink-0">
          <RadialBarChart
            width={160}
            height={160}
            innerRadius="75%"
            outerRadius="100%"
            barSize={14}
            data={data}
            startAngle={90}
            endAngle={-270}
          >
            <RadialBar background dataKey="value" cornerRadius={8} />
          </RadialBarChart>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className={cn("text-3xl font-bold tabular-nums", scoreColorClass(score.overall_score))}>
              {score.overall_score}
            </span>
            <span className="text-xs text-muted-foreground">out of 100</span>
          </div>
        </div>
        <div className="w-full space-y-2">
          {Object.entries(SUB_SCORE_LABELS).map(([key, label]) => {
            const value = score[key as keyof HealthScore] as number;
            return (
              <div key={key} className="flex items-center gap-3 text-sm">
                <span className="w-32 shrink-0 text-muted-foreground">{label}</span>
                <div className="h-1.5 flex-1 rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-1.5 rounded-full",
                      value >= 75 ? "bg-success" : value >= 50 ? "bg-warning" : "bg-danger",
                    )}
                    style={{ width: `${value}%` }}
                  />
                </div>
                <span className="w-8 text-right tabular-nums">{value}</span>
              </div>
            );
          })}
          <p className="pt-2 text-sm text-muted-foreground">{score.explanation}</p>
        </div>
      </div>
    </Card>
  );
}
