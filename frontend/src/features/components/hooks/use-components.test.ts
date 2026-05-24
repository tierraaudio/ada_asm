import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { createElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";

import { useComponents } from "./use-components";

const API = "http://localhost:8000";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return createElement(QueryClientProvider, { client }, children);
}

describe("useComponents", () => {
  it("appends multi-value filters as repeated query params", async () => {
    let captured: URL | null = null;
    server.use(
      http.get(`${API}/api/v1/components`, ({ request }) => {
        captured = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
    );

    const { result } = renderHook(
      () =>
        useComponents({
          filters: {
            q: "esp",
            families: ["Microcontroladores", "Sensores"],
            tiers: [1, 2],
            nato_scores: ["A+", "D"],
            supplier_ids: ["sup-1", "sup-2"],
          },
          page: 2,
          pageSize: 50,
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const url = captured as unknown as URL;
    expect(url.searchParams.get("q")).toBe("esp");
    expect(url.searchParams.getAll("family")).toEqual(["Microcontroladores", "Sensores"]);
    expect(url.searchParams.getAll("tier")).toEqual(["1", "2"]);
    expect(url.searchParams.getAll("nato_score")).toEqual(["A+", "D"]);
    expect(url.searchParams.getAll("supplier_id")).toEqual(["sup-1", "sup-2"]);
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("page_size")).toBe("50");
  });

  it("omits empty filters from the URL", async () => {
    let captured: URL | null = null;
    server.use(
      http.get(`${API}/api/v1/components`, ({ request }) => {
        captured = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
    );
    const { result } = renderHook(
      () => useComponents({ filters: { q: "   " }, page: 1, pageSize: 25 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const url = captured as unknown as URL;
    expect(url.searchParams.get("q")).toBeNull();
    expect(url.searchParams.getAll("family")).toEqual([]);
    expect(url.searchParams.getAll("tier")).toEqual([]);
  });
});
