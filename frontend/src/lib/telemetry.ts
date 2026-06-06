/**
 * Application Insights Web SDK bootstrap.
 *
 * Mirrors the backend's `app/infrastructure/observability.py`: a no-op
 * when `VITE_APP_INSIGHTS_CONNECTION_STRING` is absent (so `pnpm dev`
 * locally stays untouched), and a full RUM + auto page-view + W3C
 * `traceparent` propagation when set.
 *
 * Initialised from `main.tsx` BEFORE the React tree renders so the
 * first paint is already instrumented.
 */

import {
  ApplicationInsights,
  type IConfig,
  type IConfiguration,
} from "@microsoft/applicationinsights-web";

// Module-level reference so we can do a one-time init and let callers
// (e.g. error boundaries) `trackException()` later.
let appInsights: ApplicationInsights | null = null;

/**
 * Bootstrap App Insights. Safe to call multiple times — subsequent calls
 * after the first successful one are no-ops.
 *
 * @returns `true` if the SDK was wired, `false` if the connection string
 *   was absent / empty (local dev path).
 */
export function init(connectionString: string | undefined): boolean {
  if (appInsights !== null) {
    return true;
  }
  if (!connectionString || connectionString.trim() === "") {
    return false;
  }

  // The API host (where our backend lives) MUST be in
  // `correlationHeaderDomains` for the SDK to attach a `traceparent`
  // header on outgoing fetch / XHR. We derive the host from
  // `VITE_API_URL` so dev / prod work with one source of truth.
  const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  const apiHost = (() => {
    try {
      return new URL(apiBaseUrl).host;
    } catch {
      return "localhost:8000";
    }
  })();

  const config: IConfiguration & IConfig = {
    connectionString,
    // Auto page views, dependency tracking (XHR + fetch), unhandled
    // exceptions, AJAX errors — all on by default.
    enableAutoRouteTracking: true,
    enableCorsCorrelation: true,
    enableRequestHeaderTracking: false, // off — we don't want to capture Authorization headers
    enableResponseHeaderTracking: false,
    // W3C trace context: emit + accept `traceparent`. AI_AND_W3C also
    // keeps the legacy Request-Id header for cross-version
    // compatibility — we can drop this to W3C only later.
    distributedTracingMode: 2, // DistributedTracingModes.AI_AND_W3C
    correlationHeaderDomains: [apiHost],
    // Auto-flush every 15s so traces show up in App Insights faster.
    maxBatchSizeInBytes: 10_000,
    maxBatchInterval: 15_000,
    disableCookiesUsage: false, // user-session correlation needs cookies
  };

  const instance = new ApplicationInsights({ config });
  instance.loadAppInsights();
  instance.trackPageView(); // first page view
  appInsights = instance;
  return true;
}

/**
 * Returns the live App Insights instance, or `null` when `init()` was a
 * no-op. Useful for error boundaries that want to `trackException()`
 * without crashing the page when telemetry isn't configured.
 */
export function getAppInsights(): ApplicationInsights | null {
  return appInsights;
}

/**
 * Test seam: forget the cached instance so a subsequent `init()` will
 * re-wire. Only used by unit tests.
 */
export function _resetForTests(): void {
  appInsights = null;
}
