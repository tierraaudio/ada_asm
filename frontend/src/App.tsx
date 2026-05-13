import { Route, Routes } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";

const PlaceholderPage = () => (
  <div className="flex h-full items-center justify-center">
    <p className="text-base text-muted-foreground">ADA ASM placeholder</p>
  </div>
);

export const App = () => {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <DashboardLayout>
            <PlaceholderPage />
          </DashboardLayout>
        }
      />
    </Routes>
  );
};
