import { Route, Routes } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ForgotPasswordPage } from "@/features/auth/pages/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { ResetPasswordPage } from "@/features/auth/pages/ResetPasswordPage";
import { ComponentDetailPage } from "@/features/components/pages/ComponentDetailPage";
import { ComponentEditPage } from "@/features/components/pages/ComponentEditPage";
import { ComponentsListPage } from "@/features/components/pages/ComponentsListPage";
import { ModuleDetailPage } from "@/features/modules/pages/ModuleDetailPage";
import { ModuleEditPage } from "@/features/modules/pages/ModuleEditPage";
import { ModulesListPage } from "@/features/modules/pages/ModulesListPage";

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
        <Route path="/modules" element={<ModulesListPage />} />
        <Route path="/modules/new" element={<ModuleEditPage mode="create" />} />
        <Route path="/modules/:id" element={<ModuleDetailPage />} />
        <Route path="/modules/:id/edit" element={<ModuleEditPage mode="edit" />} />
        <Route path="/components" element={<ComponentsListPage />} />
        <Route path="/components/new" element={<ComponentEditPage mode="create" />} />
        <Route path="/components/:id" element={<ComponentDetailPage />} />
        <Route path="/components/:id/edit" element={<ComponentEditPage mode="edit" />} />
        <Route
          path="/notifications"
          element={<DashboardPlaceholder label="Notificaciones · próximamente" />}
        />
      </Route>
    </Routes>
  );
};
