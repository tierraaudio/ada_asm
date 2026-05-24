import type { FC, ReactNode } from "react";

import { useUiStore } from "@/lib/stores/ui-store";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export const DashboardLayout: FC<{ children: ReactNode }> = ({ children }) => {
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);

  return (
    // Use `h-screen` (not `min-h-screen`) so the sidebar can resolve `h-full`
    // against an explicit parent height; the main pane owns the scrolling.
    <div className="flex h-screen flex-col bg-page-bg text-foreground">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {!sidebarCollapsed && <Sidebar />}
        <main role="main" className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
};
