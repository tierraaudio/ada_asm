import type { FC, ReactNode } from "react";

import { useUiStore } from "@/lib/stores/ui-store";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export const DashboardLayout: FC<{ children: ReactNode }> = ({ children }) => {
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);

  return (
    <div className="flex min-h-screen flex-col bg-page-bg text-foreground">
      <Header />
      <div className="flex flex-1">
        {!sidebarCollapsed && <Sidebar />}
        <main role="main" className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  );
};
