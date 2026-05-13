import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { useAuthStore } from "@/lib/stores/auth-store";
import { clearRefreshToken, readRefreshToken, writeRefreshToken } from "@/lib/auth/token-storage";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Axios client used by every feature's API module.
 *
 * The base URL points at the backend's root (e.g. http://localhost:8000); the
 * "/api/v1" prefix is appended by each feature's calls.
 *
 * Request interceptor: attaches the in-memory access token from the Zustand
 * store. Skipped when the call already carries an Authorization header.
 *
 * Response interceptor: on a 401 the client attempts a single transparent
 * refresh. Concurrent 401s share the same refresh promise (single-flight
 * queue) so we never fire two refreshes in parallel. A second 401 after the
 * refresh attempt clears the store and routes the user to /login.
 */
export const api = axios.create({
  baseURL,
  withCredentials: false,
  timeout: 15_000,
});

const SKIP_REFRESH_URLS = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/refresh",
  "/api/v1/auth/logout",
  "/api/v1/auth/password-recovery",
  "/api/v1/auth/password-reset",
]);

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token && !config.headers?.Authorization) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

type RetryableRequest = InternalAxiosRequestConfig & { _retried?: boolean };

let inflightRefresh: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = readRefreshToken();
  if (!refreshToken) {
    return null;
  }
  try {
    const response = await axios.post(`${baseURL}/api/v1/auth/refresh`, {
      refresh_token: refreshToken,
    });
    const { access_token, refresh_token } = response.data as {
      access_token: string;
      refresh_token: string;
    };
    writeRefreshToken(refresh_token);
    return access_token;
  } catch {
    return null;
  }
}

function routeToLogin(): void {
  const next = window.location.pathname + window.location.search;
  const target = `/login?next=${encodeURIComponent(next)}`;
  if (window.location.pathname !== "/login") {
    window.location.assign(target);
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryableRequest | undefined;
    const status = error.response?.status;

    if (
      status !== 401 ||
      !original ||
      original._retried ||
      SKIP_REFRESH_URLS.has(original.url ?? "")
    ) {
      return Promise.reject(error);
    }

    if (!inflightRefresh) {
      inflightRefresh = refreshAccessToken().finally(() => {
        // Reset only after the value is consumed.
        setTimeout(() => {
          inflightRefresh = null;
        }, 0);
      });
    }

    const newAccessToken = await inflightRefresh;
    if (!newAccessToken) {
      // Refresh failed: clear local session and bounce to /login.
      useAuthStore.getState().clearSession();
      clearRefreshToken();
      routeToLogin();
      return Promise.reject(error);
    }

    // Update the store and retry the original request once.
    const store = useAuthStore.getState();
    if (store.user) {
      store.setSession(newAccessToken, store.user);
    } else {
      // Edge case: token in localStorage but no user in memory (e.g. fresh
      // tab). The caller will follow up with getMe to repopulate user.
      useAuthStore.setState({ accessToken: newAccessToken });
    }

    original._retried = true;
    original.headers = original.headers ?? {};
    (original.headers as Record<string, string>).Authorization = `Bearer ${newAccessToken}`;
    return api.request(original as AxiosRequestConfig);
  },
);
