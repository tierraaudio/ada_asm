import { Route, Routes } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ForgotPasswordPage } from "@/features/auth/pages/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { ResetPasswordPage } from "@/features/auth/pages/ResetPasswordPage";
import { ComponentDetailPage } from "@/features/components/pages/ComponentDetailPage";
import { ComponentsListPage } from "@/features/components/pages/ComponentsListPage";

const PlaceholderPage = ({ label = "ADA ASM placeholder" }: { label?: string }) => (
  <div className="flex h-full items-center justify-center">
    <p className="text-base text-text-secondary">{label}</p>
  </div>
);

const DashboardPlaceholder = ({ label }: { label?: string }) => (
  <DashboardLayout>
    {label ? <PlaceholderPage label={label} /> : <PlaceholderPage />}
  </DashboardLayout>
);

export const App = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Protected routes — destination pages land in their respective USs */}
      <Route element={<RequireAuth />}>
        <Route path="/" element={<DashboardPlaceholder />} />
        <Route
          path="/projects"
          element={<DashboardPlaceholder label="Proyectos · próximamente" />}
        />
        <Route path="/modules" element={<DashboardPlaceholder label="Módulos · próximamente" />} />
        <Route path="/components" element={<ComponentsListPage />} />
        {/* Detail / create / edit / purchases / NATO modal land in the next
            iteration — placeholders keep the routes addressable. */}
        <Route
          path="/components/new"
          element={<DashboardPlaceholder label="Nuevo componente · próximamente" />}
        />
        <Route path="/components/:id" element={<ComponentDetailPage />} />
        <Route
          path="/notifications"
          element={<DashboardPlaceholder label="Notificaciones · próximamente" />}
        />
      </Route>
    </Routes>
  );
};
