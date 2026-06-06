import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  projectsApi,
  type AddProjectChildPayload,
  type ProjectCreatePayload,
  type ProjectUpdatePayload,
  type UpdateProjectChildPayload,
} from "../api/projects-api";
import { projectDetailQueryKey } from "./use-project-detail";

/** Invalidates everything that could be impacted by a project mutation. */
function invalidateProject(qc: ReturnType<typeof useQueryClient>, id?: string) {
  qc.invalidateQueries({ queryKey: ["projects", "list"] });
  if (id) qc.invalidateQueries({ queryKey: projectDetailQueryKey(id) });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProjectCreatePayload) => projectsApi.create(payload),
    onSuccess: (created) => invalidateProject(qc, created.id),
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProjectUpdatePayload }) =>
      projectsApi.update(id, payload),
    onSuccess: (updated) => invalidateProject(qc, updated.id),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => projectsApi.softDelete(id),
    onSuccess: (_, id) => invalidateProject(qc, id),
  });
}

export function useAddProjectChild() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AddProjectChildPayload }) =>
      projectsApi.addChild(id, payload),
    onSuccess: (_, { id, payload }) => {
      invalidateProject(qc, id);
      if (payload.child_component_id) {
        qc.invalidateQueries({
          queryKey: ["components", "projects-using", payload.child_component_id],
        });
      }
      if (payload.child_module_id) {
        qc.invalidateQueries({
          queryKey: ["modules", "projects-using", payload.child_module_id],
        });
      }
    },
  });
}

export function useUpdateProjectChild() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      childId,
      payload,
    }: {
      id: string;
      childId: string;
      payload: UpdateProjectChildPayload;
    }) => projectsApi.updateChild(id, childId, payload),
    onSuccess: (_, { id }) => invalidateProject(qc, id),
  });
}

export function useRemoveProjectChild() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, childId }: { id: string; childId: string }) =>
      projectsApi.removeChild(id, childId),
    onSuccess: (_, { id }) => {
      invalidateProject(qc, id);
      // We don't know which child without an extra fetch — invalidate broadly.
      qc.invalidateQueries({ queryKey: ["components", "projects-using"] });
      qc.invalidateQueries({ queryKey: ["modules", "projects-using"] });
    },
  });
}

export function useAddInterestLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: { name: string; url: string; sort_order?: number };
    }) => projectsApi.addInterestLink(id, payload),
    onSuccess: (_, { id }) => invalidateProject(qc, id),
  });
}

export function useUpdateInterestLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      linkId,
      payload,
    }: {
      id: string;
      linkId: string;
      payload: { name?: string; url?: string; sort_order?: number };
    }) => projectsApi.updateInterestLink(id, linkId, payload),
    onSuccess: (_, { id }) => invalidateProject(qc, id),
  });
}

export function useRemoveInterestLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, linkId }: { id: string; linkId: string }) =>
      projectsApi.removeInterestLink(id, linkId),
    onSuccess: (_, { id }) => invalidateProject(qc, id),
  });
}
