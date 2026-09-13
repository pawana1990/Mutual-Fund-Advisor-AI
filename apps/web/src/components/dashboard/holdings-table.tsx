import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import type { Holding } from "@/types/api";

export function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Holdings</CardTitle>
      </CardHeader>
      {holdings.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No holdings yet — import a statement to get started.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Fund</th>
                <th className="py-2 pr-4 font-medium">AMC</th>
                <th className="py-2 pr-4 text-right font-medium">Invested</th>
                <th className="py-2 pr-4 text-right font-medium">Current</th>
                <th className="py-2 pr-4 text-right font-medium">Gain</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => {
                const gainPct = parseFloat(h.unrealized_gain_pct);
                return (
                  <tr key={h.id} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5 pr-4 font-medium">{h.fund_name}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground">{h.amc}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{formatCurrency(h.invested_value)}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{formatCurrency(h.current_value)}</td>
                    <td
                      className={cn(
                        "py-2.5 pr-4 text-right tabular-nums font-medium",
                        gainPct >= 0 ? "text-success" : "text-danger",
                      )}
                    >
                      {formatPercent(gainPct)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
