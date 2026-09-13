/** Mirrors apps/api/app/schemas/*.py — kept in one file so a backend schema
 * change is easy to diff against the frontend contract. */

export interface Portfolio {
  id: string;
  name: string;
  base_currency: string;
  owner_user_id: string;
}

export interface Holding {
  id: string;
  fund_id: string;
  fund_name: string;
  amc: string;
  category: string;
  units: string;
  avg_cost_nav: string;
  invested_value: string;
  current_value: string;
  unrealized_gain: string;
  unrealized_gain_pct: string;
}

export interface Snapshot {
  as_of: string;
  invested_value: string;
  current_value: string;
  xirr: string;
  absolute_return_pct: string;
  asset_allocation: Record<string, number>;
  sector_allocation: Record<string, number>;
  amc_allocation: Record<string, number>;
  top_holdings: Array<Record<string, unknown>>;
}

export interface HealthScore {
  overall_score: number;
  diversification_score: number;
  risk_score: number;
  returns_score: number;
  fees_score: number;
  fund_quality_score: number;
  tax_efficiency_score: number;
  asset_allocation_score: number;
  goal_readiness_score: number;
  explanation: string;
}

export type RecommendationAction = "keep" | "increase" | "reduce" | "exit" | "switch";
export type RecommendationStatus = "open" | "accepted" | "dismissed" | "superseded";

export interface Recommendation {
  id: string;
  holding_id: string | null;
  action: RecommendationAction;
  switch_target_fund_id: string | null;
  reason: string;
  supporting_metrics: Record<string, number>;
  risk: string;
  expected_benefit: string;
  confidence: number;
  status: RecommendationStatus;
  generated_by_agent: string;
}

export interface Goal {
  id: string;
  type: string;
  target_amount: string;
  target_date: string;
  required_monthly_sip: string | null;
  probability_of_success: number | null;
}

export interface Alert {
  id: string;
  type: string;
  severity: "info" | "warning" | "critical";
  title: string;
  body: string;
  read_at: string | null;
}

export interface ChatResponse {
  answer: string;
  intent: string;
  citations: Record<string, unknown>;
}
