"use client";

import { ApiError, api } from "@/lib/api-client";
import type { Alert, Goal, HealthScore, Holding, Portfolio, Recommendation, Snapshot } from "@/types/api";
import { useEffect, useState } from "react";

interface DashboardData {
  portfolio: Portfolio | null;
  snapshot: Snapshot | null;
  healthScore: HealthScore | null;
  holdings: Holding[];
  recommendations: Recommendation[];
  alerts: Alert[];
  goals: Goal[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/** Loads everything the dashboard needs for the current user's primary
 * portfolio. A GraphQL composite query (docs/API_DESIGN.md) would collapse
 * this into one round trip in production; the REST calls here are kept
 * separate and Promise.all'd so a single slow/failing endpoint (e.g. no
 * health score yet, pre-first-recompute) doesn't blank the whole page. */
export function useDashboard(): DashboardData {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [healthScore, setHealthScore] = useState<HealthScore | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const portfolios = await api.portfolios.list();
      const primary = portfolios[0] ?? null;
      setPortfolio(primary);
      if (!primary) {
        setLoading(false);
        return;
      }

      const [snapshotResult, healthScoreResult, holdingsResult, recsResult, alertsResult, goalsResult] =
        await Promise.allSettled([
          api.portfolios.snapshot(primary.id),
          api.portfolios.healthScore(primary.id),
          api.portfolios.holdings(primary.id),
          api.portfolios.recommendations(primary.id, "open"),
          api.alerts.list(true),
          api.portfolios.goals(primary.id),
        ]);

      if (snapshotResult.status === "fulfilled") setSnapshot(snapshotResult.value);
      if (healthScoreResult.status === "fulfilled") setHealthScore(healthScoreResult.value);
      if (holdingsResult.status === "fulfilled") setHoldings(holdingsResult.value);
      if (recsResult.status === "fulfilled") setRecommendations(recsResult.value);
      if (alertsResult.status === "fulfilled") setAlerts(alertsResult.value);
      if (goalsResult.status === "fulfilled") setGoals(goalsResult.value);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { portfolio, snapshot, healthScore, holdings, recommendations, alerts, goals, loading, error, refresh: load };
}
