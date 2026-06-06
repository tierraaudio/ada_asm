import type { FC, ReactNode } from "react";

import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export const DashboardLayout: FC<{ children: ReactNode }> = ({ children }) => {
  return (
    // Sidebar spans the full viewport height and owns its own top strip
    // (Singular wordmark + fold/unfold toggle). The Header lives next to it
    // in the right-hand column.
    <div className="flex h-screen bg-page-bg text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header />
        <main role="main" className="flex-1 overflow-y-auto px-6 pb-6">
          {/* No top padding here — sticky headers on detail/edit pages need
           *  to pin flush against the visible top. Pages that don't have a
           *  sticky header add their own top padding via the standard
           *  `DashboardPageContainer` patterns or with `pt-6` inline. */}
          {children}
        </main>
      </div>
    </div>
  );
};
