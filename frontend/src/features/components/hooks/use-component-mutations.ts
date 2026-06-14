import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  componentsApi,
  type ComponentCreatePayload,
  type ComponentUpdatePayload,
  type IngestComponentPayload,
} from "../api/components-api";

export function useDeleteComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => componentsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
    },
  });
}

export function useCreateComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ComponentCreatePayload) => componentsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
    },
  });
}

/** Ingest a component from its manufacturer MPN (change
 *  `ingest-component-from-mpn`). Returns the created component + a report. */
export function useIngestComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: IngestComponentPayload) => componentsApi.ingest(payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
      qc.invalidateQueries({
        queryKey: ["components", "detail", data.component.id],
      });
    },
  });
}

export function useUpdateComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ComponentUpdatePayload }) =>
      componentsApi.update(id, payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
      qc.invalidateQueries({ queryKey: ["components", "detail", data.id] });
    },
  });
}
