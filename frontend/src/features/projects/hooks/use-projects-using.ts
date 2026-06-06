import { useQuery } from "@tanstack/react-query";

import { listComponentProjectsUsing, listModuleProjectsUsing } from "../api/projects-api";

export function useComponentProjectsUsing(componentId: string | undefined) {
  return useQuery({
    queryKey: ["components", "projects-using", componentId ?? ""],
    queryFn: () => listComponentProjectsUsing(componentId as string),
    enabled: Boolean(componentId),
  });
}

export function useModuleProjectsUsing(moduleId: string | undefined) {
  return useQuery({
    queryKey: ["modules", "projects-using", moduleId ?? ""],
    queryFn: () => listModuleProjectsUsing(moduleId as string),
    enabled: Boolean(moduleId),
  });
}
