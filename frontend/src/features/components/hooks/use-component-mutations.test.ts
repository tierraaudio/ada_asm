import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { createElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";

import {
  useCreateComponent,
  useDeleteComponent,
  useSyncComponent,
  useUpdateComponent,
} from "./use-component-mutations";

const API = "http://localhost:8000";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return createElement(QueryClientProvider, { client }, children);
}

describe("component mutations", () => {
  it("useCreateComponent POSTs to /components", async () => {
    let invoked = false;
    server.use(
      http.post(`${API}/api/v1/components`, () => {
        invoked = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const { result } = renderHook(() => useCreateComponent(), { wrapper });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await result.current.mutateAsync({ mpn: "X", name: "y", family: "f", tier: "C", nato_score: "neutral", stock: 0 } as any);
    expect(invoked).toBe(true);
  });

  it("useUpdateComponent PATCHes /components/:id", async () => {
    let url: string | null = null;
    server.use(
      http.patch(`${API}/api/v1/components/:id`, ({ request }) => {
        url = request.url;
        return HttpResponse.json({ id: "abc" });
      }),
    );
    const { result } = renderHook(() => useUpdateComponent("abc"), { wrapper });
    await result.current.mutateAsync({ name: "new" });
    expect(url).toContain("/api/v1/components/abc");
  });

  it("useDeleteComponent DELETEs /components/:id", async () => {
    let invoked = false;
    server.use(
      http.delete(`${API}/api/v1/components/:id`, () => {
        invoked = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { result } = renderHook(() => useDeleteComponent(), { wrapper });
    await result.current.mutateAsync("abc");
    expect(invoked).toBe(true);
  });

  it("useSyncComponent POSTs to /components/:id/sync and returns 202 queued", async () => {
    server.use(
      http.post(`${API}/api/v1/components/:id/sync`, () =>
        HttpResponse.json({ status: "queued" }, { status: 202 }),
      ),
    );
    const { result } = renderHook(() => useSyncComponent(), { wrapper });
    const response = await result.current.mutateAsync("abc");
    await waitFor(() => expect(response.status).toBe("queued"));
  });
});
