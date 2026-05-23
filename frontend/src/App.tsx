import { Route, Routes } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ForgotPasswordPage } from "@/features/auth/pages/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { ResetPasswordPage } from "@/features/auth/pages/ResetPasswordPage";
import { ComponentDetailPage } from "@/features/components/pages/ComponentDetailPage";
import { ComponentEditPage } from "@/features/components/pages/ComponentEditPage";
import { ComponentNatoScoringPage } from "@/features/components/pages/ComponentNatoScoringPage";
import { ComponentPurchaseHistoryPage } from "@/features/components/pages/ComponentPurchaseHistoryPage";
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
        <Route path="/components/new" element={<ComponentEditPage mode="create" />} />
        <Route path="/components/:id" element={<ComponentDetailPage />} />
        <Route path="/components/:id/purchases" element={<ComponentPurchaseHistoryPage />} />
        <Route path="/components/:id/nato" element={<ComponentNatoScoringPage />} />
        <Route path="/components/:id/edit" element={<ComponentEditPage mode="edit" />} />
        <Route
          path="/notifications"
          element={<DashboardPlaceholder label="Notificaciones · próximamente" />}
        />
      </Route>
    </Routes>
  );
};
