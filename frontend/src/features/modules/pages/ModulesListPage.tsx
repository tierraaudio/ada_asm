import { Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { DataTablePagination } from "@/components/ui/data-table-pagination";
import { NATO_SCORE_VALUES, TIPO_ALMACENAMIENTO_VALUES } from "@/features/shared/enums";
import {
  FiltersDrawer,
  type FilterGroup,
  type FiltersValue,
} from "@/features/shared/filters/FiltersDrawer";
import { NATO_SCORE_LABELS } from "@/features/shared/rubrics";

import { ModulesHierarchyTable } from "../components/ModulesHierarchyTable";
import { useModules } from "../hooks/use-modules";
import { MODULE_FAMILY_VALUES, type ModuleFamilyValue, type ModuleFilters } from "../types";

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
  families?: ModuleFamilyValue[];
  nato_scores?: string[];
}

function parseFiltersFromUrl(params: URLSearchParams): PageFilters {
  const f: PageFilters = {};
  const tipos = params.getAll("tipo_almacenamiento");
  if (tipos.length) f.tipos_almacenamiento = tipos;
  const families = params.getAll("family") as ModuleFamilyValue[];
  if (families.length) f.families = families;
  const nato = params.getAll("nato_score");
  if (nato.length) f.nato_scores = nato;
  return f;
}

function writeFiltersToUrl(base: URLSearchParams, filters: PageFilters): URLSearchParams {
  const next = new URLSearchParams(base);
  ["tipo_almacenamiento", "family", "nato_score"].forEach((k) => next.delete(k));
  for (const t of filters.tipos_almacenamiento ?? []) next.append("tipo_almacenamiento", t);
  for (const f of filters.families ?? []) next.append("family", f);
  for (const n of filters.nato_scores ?? []) next.append("nato_score", n);
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

  // Client-side filtering — the BE filters by `q` only. The combined chip
  // count stays visible to the user via the drawer.
  const filteredItems = useMemo(() => {
    const items = query.data?.items ?? [];
    let out = items;
    if (urlFilters.tipos_almacenamiento?.length) {
      const allowed = new Set(urlFilters.tipos_almacenamiento);
      out = out.filter((m) => m.tipo_almacenamiento && allowed.has(m.tipo_almacenamiento));
    }
    if (urlFilters.families?.length) {
      const allowed = new Set<ModuleFamilyValue>(urlFilters.families);
      out = out.filter((m) => allowed.has(m.family));
    }
    if (urlFilters.nato_scores?.length) {
      const allowed = new Set(urlFilters.nato_scores);
      out = out.filter((m) => m.aggregated_nato_score && allowed.has(m.aggregated_nato_score));
    }
    return out;
  }, [query.data, urlFilters]);

  const filterGroups: FilterGroup[] = useMemo(
    () => [
      {
        key: "families",
        title: "Familia",
        options: MODULE_FAMILY_VALUES.map((v) => ({ value: v, label: v })),
      },
      {
        key: "nato_scores",
        title: "Scoring OTAN",
        options: NATO_SCORE_VALUES.map((s) => ({ value: s, label: NATO_SCORE_LABELS[s] })),
      },
      {
        key: "tipos_almacenamiento",
        title: "Tipo almacenamiento",
        options: TIPO_ALMACENAMIENTO_VALUES.map((t) => ({ value: t, label: t })),
      },
    ],
    [],
  );

  const drawerValue: FiltersValue = useMemo(
    () => ({
      families: urlFilters.families ?? [],
      nato_scores: urlFilters.nato_scores ?? [],
      tipos_almacenamiento: urlFilters.tipos_almacenamiento ?? [],
    }),
    [urlFilters],
  );

  function applyFilters(next: FiltersValue) {
    const filters: PageFilters = {};
    const families = (next.families as string[] | undefined) ?? [];
    const natoScores = (next.nato_scores as string[] | undefined) ?? [];
    const tipos = (next.tipos_almacenamiento as string[] | undefined) ?? [];
    if (families.length) filters.families = families as ModuleFamilyValue[];
    if (natoScores.length) filters.nato_scores = natoScores;
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
      <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-6 pt-6">
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
            legend="Combinan con AND. Cada bloque acumula con OR."
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
