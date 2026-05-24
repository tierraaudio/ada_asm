import { Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";

import { ModulesHierarchyTable } from "../components/ModulesHierarchyTable";
import { useModules } from "../hooks/use-modules";

export function ModulesListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const filters = useMemo(() => ({ q: search }), [search]);
  const query = useModules(filters, 1, 100);

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-6">
        <header className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-text-primary">Módulos</h1>
            <p className="text-sm text-text-secondary">
              Gestiona los módulos y su estructura jerárquica de componentes
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            onClick={() => navigate("/modules/new")}
            className="bg-brand text-white hover:bg-brand/90"
          >
            <Plus className="size-4" />
            Nuevo módulo
          </Button>
        </header>

        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-secondary" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar módulos…"
            className="h-10 w-full rounded-md border border-border bg-white pl-10 pr-3 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
          />
        </div>

        {query.isLoading ? (
          <p className="text-sm text-text-secondary">Cargando módulos…</p>
        ) : (
          <ModulesHierarchyTable rows={query.data?.items ?? []} />
        )}
      </div>
    </DashboardLayout>
  );
}
