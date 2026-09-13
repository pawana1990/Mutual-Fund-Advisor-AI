"use client";

import { Badge, actionVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import type { Recommendation } from "@/types/api";
import { useState } from "react";

/** Every recommendation always shows its evidence — see
 * docs/AI_AGENT_WORKFLOW.md §4: the product never asserts an action
 * without the reason, risk, and expected benefit that back it. */
export function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  const [status, setStatus] = useState(recommendation.status);
  const [busy, setBusy] = useState(false);

  async function handle(action: "accept" | "dismiss") {
    setBusy(true);
    try {
      const updated =
        action === "accept"
          ? await api.recommendations.accept(recommendation.id)
          : await api.recommendations.dismiss(recommendation.id);
      setStatus(updated.status);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant={actionVariant(recommendation.action)}>{recommendation.action.toUpperCase()}</Badge>
        <span className="text-xs text-muted-foreground">
          {Math.round(recommendation.confidence * 100)}% confidence
        </span>
      </div>
      <p className="text-sm">{recommendation.reason}</p>
      <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <p>
          <span className="font-medium text-foreground">Risk: </span>
          {recommendation.risk}
        </p>
        <p>
          <span className="font-medium text-foreground">Expected benefit: </span>
          {recommendation.expected_benefit}
        </p>
      </div>
      {Object.keys(recommendation.supporting_metrics).length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(recommendation.supporting_metrics).map(([key, value]) => (
            <Badge key={key} variant="muted">
              {key.replace(/_/g, " ")}: {typeof value === "number" ? value.toFixed(2) : String(value)}
            </Badge>
          ))}
        </div>
      )}
      {status === "open" ? (
        <div className="flex gap-2 pt-1">
          <Button size="sm" disabled={busy} onClick={() => handle("accept")}>
            Accept
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => handle("dismiss")}>
            Dismiss
          </Button>
        </div>
      ) : (
        <Badge variant="muted">{status}</Badge>
      )}
    </Card>
  );
}
