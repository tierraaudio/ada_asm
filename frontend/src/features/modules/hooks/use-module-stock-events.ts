import { useQuery } from "@tanstack/react-query";

import { modulesApi } from "../api/modules-api";

export function moduleStockEventsQueryKey(moduleId: string) {
  return ["modules", "stock-events", moduleId] as const;
}

export function useModuleStockEvents(moduleId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: moduleStockEventsQueryKey(moduleId ?? ""),
    queryFn: () => modulesApi.listStockEvents(moduleId as string),
    enabled: Boolean(moduleId) && enabled,
  });
}

export function moduleComponentPurchasesSummaryQueryKey(moduleId: string) {
  return ["modules", "component-purchases-summary", moduleId] as const;
}

export function useModuleComponentPurchasesSummary(moduleId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: moduleComponentPurchasesSummaryQueryKey(moduleId ?? ""),
    queryFn: () => modulesApi.listComponentPurchasesSummary(moduleId as string),
    enabled: Boolean(moduleId) && enabled,
  });
}
