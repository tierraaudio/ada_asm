import { Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { DataTablePagination } from "@/components/ui/data-table-pagination";
import {
  FiltersDrawer,
  type FilterGroup,
  type FiltersValue,
} from "@/features/shared/filters/FiltersDrawer";
import { TIPO_ALMACENAMIENTO_VALUES } from "@/features/shared/enums";

import { ModulesHierarchyTable } from "../components/ModulesHierarchyTable";
import { useModules } from "../hooks/use-modules";
import type { ModuleFilters } from "../types";

const PAGE_SIZE = 25;

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

interface PageFilters extends ModuleFilters {
  tipos_almacenamiento?: string[];
}

function parseFiltersFromUrl(params: URLSearchParams): PageFilters {
  const f: PageFilters = {};
  const tipos = params.getAll("tipo_almacenamiento");
  if (tipos.length) f.tipos_almacenamiento = tipos;
  return f;
}

function writeFiltersToUrl(base: URLSearchParams, filters: PageFilters): URLSearchParams {
  const next = new URLSearchParams(base);
  next.delete("tipo_almacenamiento");
  for (const t of filters.tipos_almacenamiento ?? []) next.append("tipo_almacenamiento", t);
  next.delete("page");
  return next;
}

export function ModulesListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const debouncedQ = useDebounced(searchInput);

  const urlFilters = useMemo(() => parseFiltersFromUrl(searchParams), [searchParams]);
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const apiFilters: ModuleFilters = useMemo(() => {
    const f: ModuleFilters = {};
    if (debouncedQ.trim()) f.q = debouncedQ.trim();
    return f;
  }, [debouncedQ]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    const current = searchParams.get("q") ?? "";
    if (debouncedQ.trim() === current.trim()) return;
    if (debouncedQ.trim()) next.set("q", debouncedQ.trim());
    else next.delete("q");
    next.delete("page");
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ]);

  const query = useModules(apiFilters, page, PAGE_SIZE);
  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Filter client-side by tipo_almacenamiento (no BE filter yet; cheap and
  // matches the current page size).
  const filteredItems = useMemo(() => {
    const items = query.data?.items ?? [];
    if (!urlFilters.tipos_almacenamiento?.length) return items;
    const allowed = new Set(urlFilters.tipos_almacenamiento);
    return items.filter((m) => m.tipo_almacenamiento && allowed.has(m.tipo_almacenamiento));
  }, [query.data, urlFilters.tipos_almacenamiento]);

  const filterGroups: FilterGroup[] = useMemo(
    () => [
      {
        key: "tipos_almacenamiento",
        title: "Tipo almacenamiento",
        options: TIPO_ALMACENAMIENTO_VALUES.map((t) => ({ value: t, label: t })),
      },
    ],
    [],
  );

  const drawerValue: FiltersValue = useMemo(
    () => ({ tipos_almacenamiento: urlFilters.tipos_almacenamiento ?? [] }),
    [urlFilters.tipos_almacenamiento],
  );

  function applyFilters(next: FiltersValue) {
    const tipos = (next.tipos_almacenamiento as string[] | undefined) ?? [];
    const filters: PageFilters = {};
    if (tipos.length) filters.tipos_almacenamiento = tipos;
    setSearchParams(writeFiltersToUrl(searchParams, filters), { replace: false });
  }

  function clearFilters() {
    setSearchParams(writeFiltersToUrl(searchParams, {}), { replace: false });
  }

  function gotoPage(target: number) {
    const next = new URLSearchParams(searchParams);
    if (target <= 1) next.delete("page");
    else next.set("page", String(target));
    setSearchParams(next);
  }

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-6">
        <header>
          <h1 className="text-3xl font-semibold text-text-primary">Módulos</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Gestiona los módulos y su estructura jerárquica de componentes
          </p>
        </header>

        <div className="flex items-center gap-3">
          <label htmlFor="modules-search" className="sr-only">
            Buscar módulos
          </label>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-secondary" />
            <input
              id="modules-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar por SKU, nombre o descripción…"
              className="h-10 w-full rounded-md border border-input bg-white pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            />
          </div>
          <FiltersDrawer
            groups={filterGroups}
            value={drawerValue}
            onApply={applyFilters}
            onClear={clearFilters}
            legend="Filtra por tipo de almacenamiento."
          />
          <Button
            type="button"
            variant="outline"
            className="h-10"
            onClick={() => navigate("/modules/new")}
          >
            <Plus className="size-4" />
            Nuevo
          </Button>
        </div>

        <section>
          {query.isLoading ? (
            <div className="rounded-md border border-border bg-white p-8 text-center text-sm text-text-secondary">
              Cargando…
            </div>
          ) : query.isError ? (
            <div className="rounded-md border border-border bg-white p-8 text-center text-sm text-destructive">
              No se pudo cargar el catálogo.
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-md border border-border bg-white p-12 text-center">
              <p className="text-base font-medium text-text-primary">Sin módulos</p>
              <p className="text-sm text-text-secondary">
                Ajusta los filtros o crea el primer módulo.
              </p>
            </div>
          ) : (
            <ModulesHierarchyTable rows={filteredItems} />
          )}
        </section>

        <DataTablePagination
          page={page}
          pageCount={pageCount}
          total={total}
          onPageChange={gotoPage}
        />
      </div>
    </DashboardLayout>
  );
}
