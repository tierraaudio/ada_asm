import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";

// Node 25 ships an experimental native localStorage that does not implement
// the full Storage interface and shadows jsdom's shim. Replace it with a
// minimal in-memory Storage so the rest of the suite (which relies on the
// real Storage API: setItem/getItem/removeItem/clear/length/key) works.
class MemoryStorage implements Storage {
  private store: Map<string, string> = new Map();
  get length(): number {
    return this.store.size;
  }
  clear(): void {
    this.store.clear();
  }
  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }
}

if (typeof window !== "undefined") {
  Object.defineProperty(window, "localStorage", {
    value: new MemoryStorage(),
    configurable: true,
    writable: false,
  });
  Object.defineProperty(window, "sessionStorage", {
    value: new MemoryStorage(),
    configurable: true,
    writable: false,
  });
}

/** MSW request handlers — features add their own per-test via `server.use(...)`. */
export const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

// Reset localStorage and the auth store between tests so cases are
// independent. Imported lazily to avoid pulling app modules into the setup
// file before tests opt in.
beforeEach(async () => {
  window.localStorage.clear();
  const { useAuthStore } = await import("@/lib/stores/auth-store");
  useAuthStore.setState({ accessToken: null, user: null, status: "anonymous" });
});
