import { type FC } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuthStore } from "@/lib/stores/auth-store";

export const RequireAuth: FC = () => {
  const status = useAuthStore((s) => s.status);
  const location = useLocation();

  if (status !== "authenticated") {
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return <Outlet />;
};
