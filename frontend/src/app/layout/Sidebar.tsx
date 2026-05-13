import type { FC } from "react";

export const Sidebar: FC = () => {
  return (
    <aside
      role="navigation"
      aria-label="Primary"
      data-testid="app-sidebar"
      className="hidden w-64 shrink-0 border-r border-border bg-muted/30 lg:block"
    >
      <nav className="p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Navigation
        </p>
        <ul className="mt-2 space-y-1 text-sm text-foreground">
          <li>Proyectos</li>
          <li>Módulos</li>
          <li>Componentes</li>
        </ul>
      </nav>
    </aside>
  );
};
