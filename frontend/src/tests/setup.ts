import "@testing-library/jest-dom/vitest";

import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll } from "vitest";

/** MSW request handlers — empty for now; features add their own. */
export const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
