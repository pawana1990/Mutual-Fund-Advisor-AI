import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { Alert } from "@/types/api";
import { AlertTriangle, Info, OctagonAlert } from "lucide-react";

const SEVERITY_ICON = {
  info: Info,
  warning: AlertTriangle,
  critical: OctagonAlert,
} as const;

const SEVERITY_VARIANT = {
  info: "muted",
  warning: "warning",
  critical: "danger",
} as const;

export function AlertsList({ alerts }: { alerts: Alert[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Alerts</CardTitle>
      </CardHeader>
      {alerts.length === 0 ? (
        <p className="text-sm text-muted-foreground">You&apos;re all caught up — no active alerts.</p>
      ) : (
        <ul className="space-y-3">
          {alerts.map((alert) => {
            const Icon = SEVERITY_ICON[alert.severity];
            return (
              <li key={alert.id} className="flex items-start gap-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                <div className="flex-1 space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{alert.title}</span>
                    <Badge variant={SEVERITY_VARIANT[alert.severity]}>{alert.severity}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{alert.body}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
