import { useMutation, useQueryClient } from "@tanstack/react-query";

import { componentsApi } from "../api/components-api";

export function useDeleteComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => componentsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["components", "list"] });
    },
  });
}
