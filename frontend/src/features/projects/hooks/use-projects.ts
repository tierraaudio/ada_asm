import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { projectsApi } from "../api/projects-api";
import type { ProjectFilters } from "../types";

export function projectsListQueryKey(filters: ProjectFilters, page: number, pageSize: number) {
  return [
    "projects",
    "list",
    {
      q: filters.q ?? null,
      statuses: filters.statuses ?? null,
      customer_ids: filters.customer_ids ?? null,
      include_archived: !!filters.include_archived,
      page,
      pageSize,
    },
  ] as const;
}

export function useProjects(filters: ProjectFilters, page = 1, pageSize = 25) {
  return useQuery({
    queryKey: projectsListQueryKey(filters, page, pageSize),
    queryFn: () => projectsApi.list(filters, page, pageSize),
    placeholderData: keepPreviousData,
  });
}
