import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Axios client used by every feature's API module.
 *
 * The base URL points at the backend's root (e.g. http://localhost:8000); the
 * "/api/v1" prefix is appended by each feature's calls. Auth interceptors are
 * intentionally not wired here — they land with the Login user story.
 */
export const api = axios.create({
  baseURL,
  withCredentials: false,
  timeout: 15_000,
});
