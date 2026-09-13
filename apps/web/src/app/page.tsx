"use client";

import { AllocationChart } from "@/components/dashboard/allocation-chart";
import { AlertsList } from "@/components/dashboard/alerts-list";
import { ChatPanel } from "@/components/dashboard/chat-panel";
import { HealthScoreGauge } from "@/components/dashboard/health-score-gauge";
import { HoldingsTable } from "@/components/dashboard/holdings-table";
import { RecommendationCard } from "@/components/dashboard/recommendation-card";
import { StatCard } from "@/components/dashboard/stat-card";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { api } from "@/lib/api-client";
import { useDashboard } from "@/hooks/use-dashboard";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { RefreshCw, TrendingUp, Wallet } from "lucide-react";
import { useState } from "react";

export default function DashboardPage() {
  const { portfolio, snapshot, healthScore, holdings, recommendations, alerts, loading, error, refresh } =
    useDashboard();
  const [recomputing, setRecomputing] = useState(false);

  async function handleRecompute() {
    if (!portfolio) return;
    setRecomputing(true);
    try {
      await api.portfolios.recompute(portfolio.id);
      await refresh();
    } finally {
      setRecomputing(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">AI Wealth Advisor</h1>
          <p className="text-sm text-muted-foreground">{portfolio?.name ?? "Your portfolio"}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRecompute} disabled={recomputing || !portfolio}>
            <RefreshCw className={recomputing ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            {recomputing ? "Refreshing…" : "Refresh analysis"}
          </Button>
          <ThemeToggle />
        </div>
      </header>

      {loading && <p className="text-sm text-muted-foreground">Loading your portfolio…</p>}
      {error && <p className="text-sm text-danger">{error}</p>}

      {!loading && !error && !portfolio && (
        <div className="rounded-lg border border-dashed border-border p-10 text-center text-muted-foreground">
          <p className="font-medium">No portfolio yet</p>
          <p className="text-sm">Import a CAMS/KFin/Groww statement to get started.</p>
        </div>
      )}

      {portfolio && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatCard
                label="Portfolio Value"
                value={snapshot ? formatCurrency(snapshot.current_value) : "—"}
                icon={Wallet}
              />
              <StatCard
                label="Invested"
                value={snapshot ? formatCurrency(snapshot.invested_value) : "—"}
              />
              <StatCard
                label="Profit"
                value={
                  snapshot
                    ? formatCurrency(parseFloat(snapshot.current_value) - parseFloat(snapshot.invested_value))
                    : "—"
                }
                delta={snapshot ? formatPercent(snapshot.absolute_return_pct) : undefined}
                deltaTone={
                  snapshot && parseFloat(snapshot.absolute_return_pct) >= 0 ? "positive" : "negative"
                }
                icon={TrendingUp}
              />
              <StatCard label="XIRR" value={snapshot ? formatPercent(snapshot.xirr) : "—"} />
            </div>

            {healthScore && <HealthScoreGauge score={healthScore} />}

            {snapshot && (
              <div className="grid gap-4 sm:grid-cols-2">
                <AllocationChart title="Asset Allocation" data={snapshot.asset_allocation} />
                <AllocationChart title="AMC Allocation" data={snapshot.amc_allocation} />
              </div>
            )}

            <HoldingsTable holdings={holdings} />

            <section>
              <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Recommendations</h2>
              {recommendations.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No open recommendations — run &ldquo;Refresh analysis&rdquo; after your next import.
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {recommendations.map((rec) => (
                    <RecommendationCard key={rec.id} recommendation={rec} />
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="space-y-6">
            <AlertsList alerts={alerts} />
            <div className="h-[420px]">
              <ChatPanel portfolioId={portfolio.id} />
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
