import { AlertTriangle, Info, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils/cn";

import { computeAlerts } from "../alerts";
import type { Component, ComponentPurchase } from "../types";

const ICON = {
  info: Info,
  warning: AlertTriangle,
  critical: ShieldAlert,
} as const;

const STYLES = {
  info: "border-sky-200 bg-sky-50 text-sky-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  critical: "border-red-200 bg-red-50 text-red-800",
} as const;

export function ComponentAlertsPanel({
  component,
  purchases,
}: {
  component: Component;
  purchases: ComponentPurchase[];
}) {
  const alerts = computeAlerts(component, purchases);
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
        Alertas
      </h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-text-secondary">Sin alertas activas.</p>
      ) : (
        <ul className="space-y-2">
          {alerts.map((alert) => {
            const Icon = ICON[alert.severity];
            return (
              <li
                key={alert.id}
                className={cn(
                  "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
                  STYLES[alert.severity],
                )}
              >
                <Icon className="mt-0.5 size-4 shrink-0" />
                <span>{alert.message}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
