import { useQuery } from "@tanstack/react-query";

import { projectsApi } from "../api/projects-api";

export function useProjectPriceHistory(
  id: string | undefined,
  period: "week" | "month" | "year" = "year",
  enabled = true,
) {
  return useQuery({
    queryKey: ["projects", "price-history", id ?? "", period],
    queryFn: () => projectsApi.listPriceHistory(id as string, period),
    enabled: Boolean(id) && enabled,
  });
}

export function useProjectStockEvents(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["projects", "stock-events", id ?? ""],
    queryFn: () => projectsApi.listStockEvents(id as string),
    enabled: Boolean(id) && enabled,
  });
}
