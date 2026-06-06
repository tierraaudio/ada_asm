import { Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { DataTablePagination } from "@/components/ui/data-table-pagination";
import { TruncatedText } from "@/features/shared/ui/TruncatedText";
import { NatoScoreBadge } from "@/features/shared/badges/NatoScoreBadge";
import {
  FiltersDrawer,
  type FilterGroup,
  type FiltersValue,
} from "@/features/shared/filters/FiltersDrawer";
import { formatEuros } from "@/lib/format/currency";

import { CustomerLink } from "../components/CustomerLink";
import { ProjectStatusBadge } from "../components/ProjectStatusBadge";
import { useCustomers } from "../hooks/use-customers";
import { useProjects } from "../hooks/use-projects";
import {
  PROJECT_STATUS_VALUES,
  type ProjectFilters,
  type ProjectStatus,
  type ProjectSummary,
} from "../types";

const PAGE_SIZE = 25;

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

interface PageFilters {
  statuses?: ProjectStatus[];
  customer_ids?: string[];
  include_archived?: boolean;
}

function parseFiltersFromUrl(params: URLSearchParams): PageFilters {
  const f: PageFilters = {};
  const statuses = params
    .getAll("status")
    .filter((s): s is ProjectStatus => (PROJECT_STATUS_VALUES as readonly string[]).includes(s));
  if (statuses.length) f.statuses = statuses;
  const customers = params.getAll("customer_id");
  if (customers.length) f.customer_ids = customers;
  if (params.get("include_archived") === "true") f.include_archived = true;
  return f;
}

function writeFiltersToUrl(base: URLSearchParams, filters: PageFilters): URLSearchParams {
  const next = new URLSearchParams(base);
  ["status", "customer_id"].forEach((k) => next.delete(k));
  next.delete("include_archived");
  for (const s of filters.statuses ?? []) next.append("status", s);
  for (const c of filters.customer_ids ?? []) next.append("customer_id", c);
  if (filters.include_archived) next.set("include_archived", "true");
  next.delete("page");
  return next;
}

function formatDdMmYyyy(iso: string | null | undefined): string {
  if (!iso) return "—";
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

export function ProjectsListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const debouncedQ = useDebounced(searchInput);

  const urlFilters = useMemo(() => parseFiltersFromUrl(searchParams), [searchParams]);
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const apiFilters: ProjectFilters = useMemo(() => {
    const f: ProjectFilters = {};
    if (debouncedQ.trim()) f.q = debouncedQ.trim();
    if (urlFilters.statuses?.length) f.statuses = urlFilters.statuses;
    if (urlFilters.customer_ids?.length) f.customer_ids = urlFilters.customer_ids;
    if (urlFilters.include_archived) f.include_archived = true;
    return f;
  }, [debouncedQ, urlFilters]);

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

  const query = useProjects(apiFilters, page, PAGE_SIZE);
  const customersQuery = useCustomers();
  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const items = query.data?.items ?? [];

  const filterGroups: FilterGroup[] = useMemo(
    () => [
      {
        key: "statuses",
        title: "Estado",
        options: PROJECT_STATUS_VALUES.map((v) => ({ value: v, label: v })),
      },
      {
        key: "customer_ids",
        title: "Cliente",
        options: (customersQuery.data ?? []).map((c) => ({ value: c.id, label: c.name })),
      },
      {
        key: "include_archived",
        title: "Archivados",
        options: [{ value: "true", label: "Incluir archivados" }],
      },
    ],
    [customersQuery.data],
  );

  const drawerValue: FiltersValue = useMemo(
    () => ({
      statuses: urlFilters.statuses ?? [],
      customer_ids: urlFilters.customer_ids ?? [],
      include_archived: urlFilters.include_archived ? ["true"] : [],
    }),
    [urlFilters],
  );

  function applyFilters(next: FiltersValue) {
    const filters: PageFilters = {};
    const statuses = (next.statuses as string[] | undefined) ?? [];
    const customers = (next.customer_ids as string[] | undefined) ?? [];
    const includeArchivedList = (next.include_archived as string[] | undefined) ?? [];
    if (statuses.length) filters.statuses = statuses as ProjectStatus[];
    if (customers.length) filters.customer_ids = customers;
    if (includeArchivedList.includes("true")) filters.include_archived = true;
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
          <h1 className="text-3xl font-semibold text-text-primary">Proyectos</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Lista de proyectos activos, entregados y en draft. Los archivados se muestran solo
            cuando lo pides explícitamente.
          </p>
        </header>

        <div className="flex items-center gap-3">
          <label htmlFor="projects-search" className="sr-only">
            Buscar proyectos
          </label>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-secondary" />
            <input
              id="projects-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar por código, nombre o cliente…"
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
            onClick={() => navigate("/projects/new")}
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
              No se pudo cargar la lista de proyectos.
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-md border border-border bg-white p-12 text-center">
              <p className="text-base font-medium text-text-primary">Sin proyectos</p>
              <p className="text-sm text-text-secondary">
                Ajusta los filtros o crea el primer proyecto.
              </p>
            </div>
          ) : (
            <ProjectsTable
              items={items}
              onView={(id) => navigate(`/projects/${id}`)}
            />
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

interface ProjectsTableProps {
  items: ProjectSummary[];
  onView: (id: string) => void;
}

function ProjectsTable({ items, onView }: ProjectsTableProps) {
  return (
    <div className="overflow-hidden rounded-md border border-border bg-white">
      <table className="w-full table-fixed text-sm">
        <colgroup>
          {/* Icon + name composite (Proyecto), then Clave, Estado, Contacto,
              Fecha inicio, Versión, Precio, NATO. Row click navigates to detail —
              no Acciones column anymore. */}
          <col className="w-[28%]" />
          <col className="w-[10%]" />
          <col className="w-[13%]" />
          <col className="w-[16%]" />
          <col className="w-[10%]" />
          <col className="w-[7%]" />
          <col className="w-[8%]" />
          <col className="w-[8%]" />
        </colgroup>
        <thead>
          <tr className="bg-muted/30 text-xs font-bold uppercase tracking-wide text-text-secondary">
            <th className="px-3 py-2 text-left">Proyecto</th>
            <th className="px-3 py-2 text-left">Clave</th>
            <th className="px-3 py-2 text-left">Estado</th>
            <th className="px-3 py-2 text-left">Contacto</th>
            <th className="px-3 py-2 text-left">Fecha inicio</th>
            <th className="px-3 py-2 text-left">Versión</th>
            <th className="px-3 py-2 text-left">Precio</th>
            <th className="px-3 py-2 text-left">NATO</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr
              key={p.id}
              role="button"
              tabIndex={0}
              onClick={() => onView(p.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onView(p.id);
                }
              }}
              className="cursor-pointer border-t border-border hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/40"
            >
              <td className="overflow-hidden px-3 py-2">
                <div className="flex items-start gap-3">
                  <span
                    aria-hidden
                    className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-base"
                    style={{
                      backgroundColor: p.color ? `${p.color}1a` : undefined,
                      color: p.color ?? undefined,
                    }}
                  >
                    {p.icon ?? "📁"}
                  </span>
                  <div className="min-w-0">
                    <TruncatedText
                      as="p"
                      text={p.name}
                      className="text-sm font-medium text-text-primary"
                    />
                    {p.description && (
                      <TruncatedText
                        as="p"
                        text={p.description}
                        className="text-xs text-text-secondary"
                      />
                    )}
                  </div>
                </div>
              </td>
              <td className="px-3 py-2 font-mono text-xs text-text-secondary">{p.code}</td>
              <td className="px-3 py-2">
                <ProjectStatusBadge value={p.status} />
              </td>
              <td className="overflow-hidden px-3 py-2">
                {p.customer ? <CustomerLink customer={p.customer} compact /> : "—"}
              </td>
              <td className="px-3 py-2 text-text-secondary">
                {formatDdMmYyyy(p.fecha_inicio)}
              </td>
              <td className="px-3 py-2 text-text-secondary">{p.version ?? "—"}</td>
              <td className="px-3 py-2 font-semibold text-brand">
                {p.precio_total != null ? formatEuros(p.precio_total) : "—"}
              </td>
              <td className="px-3 py-2">
                {p.aggregated_nato_score ? (
                  <NatoScoreBadge value={p.aggregated_nato_score} />
                ) : (
                  <span className="text-xs text-text-secondary">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
