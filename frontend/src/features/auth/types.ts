/**
 * Shape of the authenticated user, mirroring the backend's MeResponse.
 * Keep the schema aligned with `backend/app/api/v1/schemas/auth.py::MeResponse`.
 */
export type GlobalRole = "admin" | "user";

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  global_role: GlobalRole;
  is_active: boolean;
  created_at: string;
};
