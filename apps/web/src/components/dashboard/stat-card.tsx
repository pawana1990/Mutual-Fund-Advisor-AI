import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "positive" | "negative" | "neutral";
  icon?: LucideIcon;
}

export function StatCard({ label, value, delta, deltaTone = "neutral", icon: Icon }: StatCardProps) {
  return (
    <Card className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
        {Icon ? <Icon className="h-4 w-4 text-muted-foreground" aria-hidden /> : null}
      </div>
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      {delta ? (
        <span
          className={cn(
            "text-xs font-medium",
            deltaTone === "positive" && "text-success",
            deltaTone === "negative" && "text-danger",
            deltaTone === "neutral" && "text-muted-foreground",
          )}
        >
          {delta}
        </span>
      ) : null}
    </Card>
  );
}
