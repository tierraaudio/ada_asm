import type { FC, ReactNode } from "react";

import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export const DashboardLayout: FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main role="main" className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  );
};
