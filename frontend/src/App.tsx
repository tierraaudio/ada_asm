import { Route, Routes } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ForgotPasswordPage } from "@/features/auth/pages/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { ResetPasswordPage } from "@/features/auth/pages/ResetPasswordPage";

const PlaceholderPage = () => (
  <div className="flex h-full items-center justify-center">
    <p className="text-base text-text-secondary">ADA ASM placeholder</p>
  </div>
);

export const App = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Protected routes */}
      <Route element={<RequireAuth />}>
        <Route
          path="/"
          element={
            <DashboardLayout>
              <PlaceholderPage />
            </DashboardLayout>
          }
        />
      </Route>
    </Routes>
  );
};
