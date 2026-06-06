import { useQuery } from "@tanstack/react-query";

import { projectsApi } from "../api/projects-api";

export function projectDetailQueryKey(id: string) {
  return ["projects", "detail", id] as const;
}

export function useProjectDetail(id: string | undefined) {
  return useQuery({
    queryKey: projectDetailQueryKey(id ?? ""),
    queryFn: () => projectsApi.get(id as string),
    enabled: Boolean(id),
  });
}
