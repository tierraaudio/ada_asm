import { Eye, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { DataTablePagination } from "@/components/ui/data-table-pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatEuros } from "@/lib/format/currency";
import { cn } from "@/lib/utils/cn";

import { ComponentsFiltersDrawer } from "../components/ComponentsFiltersDrawer";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { NatoScoreBadge } from "../components/NatoScoreBadge";
import { NatoScoreHelpPopover } from "../components/NatoScoreHelpPopover";
import { StockStatusBadge } from "../components/StockStatusBadge";
import { iconForFamily } from "../family-icons";
import { useDeleteComponent } from "../hooks/use-component-mutations";
import { useComponents } from "../hooks/use-components";
import { useSuppliers } from "../hooks/use-suppliers";
import {
  effectiveStockMin,
  type Component,
  type ComponentFilters,
  type NatoScoreValue,
  type TierValue,
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

function parseFiltersFromUrl(params: URLSearchParams): ComponentFilters {
  const f: ComponentFilters = {};
  const families = params.getAll("family");
  if (families.length) f.families = families;
  const suppliers = params.getAll("supplier_id");
  if (suppliers.length) f.supplier_ids = suppliers;
  const tiers = params
    .getAll("tier")
    .map((t) => Number(t) as TierValue)
    .filter((t) => [1, 2, 3, 4].includes(t));
  if (tiers.length) f.tiers = tiers;
  const nato = params.getAll("nato_score") as NatoScoreValue[];
  if (nato.length) f.nato_scores = nato;
  return f;
}

function writeFiltersToUrl(base: URLSearchParams, filters: ComponentFilters): URLSearchParams {
  const next = new URLSearchParams(base);
  // Drop multi-value keys we own.
  ["family", "supplier_id", "tier", "nato_score"].forEach((k) => next.delete(k));
  for (const f of filters.families ?? []) next.append("family", f);
  for (const s of filters.supplier_ids ?? []) next.append("supplier_id", s);
  for (const t of filters.tiers ?? []) next.append("tier", String(t));
  for (const n of filters.nato_scores ?? []) next.append("nato_score", n);
  next.delete("page");
  return next;
}

export function ComponentsListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const debouncedQ = useDebounced(searchInput);

  const urlFilters = useMemo(() => parseFiltersFromUrl(searchParams), [searchParams]);
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const filters: ComponentFilters = useMemo(() => {
    const f: ComponentFilters = { ...urlFilters };
    if (debouncedQ.trim()) f.q = debouncedQ.trim();
    return f;
  }, [urlFilters, debouncedQ]);

  // Keep ?q= in the URL up to date with the debounced search input.
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

  const componentsQuery = useComponents({ filters, page, pageSize: PAGE_SIZE });
  const suppliersQuery = useSuppliers();
  const deleteMutation = useDeleteComponent();

  const items = useMemo(() => componentsQuery.data?.items ?? [], [componentsQuery.data]);
  const total = componentsQuery.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Families derived from the visible page — good enough for the filter chips
  // until we expose a dedicated /distinct-families endpoint.
  const familyOptions = useMemo(
    () => Array.from(new Set(items.map((c) => c.family))).sort(),
    [items],
  );

  function applyFilters(next: ComponentFilters) {
    setSearchParams(writeFiltersToUrl(searchParams, next), { replace: false });
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
          <h1 className="text-3xl font-semibold text-text-primary">Componentes</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Gestiona los componentes electrónicos y su inventario
          </p>
        </header>

        <div className="flex items-center gap-3">
          <label htmlFor="components-search" className="sr-only">
            Buscar componentes
          </label>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-secondary" />
            <input
              id="components-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar por MPN, SKU, nombre o familia…"
              className="h-10 w-full rounded-md border border-input bg-white pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            />
          </div>
          <ComponentsFiltersDrawer
            value={urlFilters}
            onApply={applyFilters}
            onClear={clearFilters}
            familyOptions={familyOptions}
            suppliers={suppliersQuery.data ?? []}
          />
          <Button type="button" variant="default" className="h-10">
            <RefreshCw className="size-4" />
            Sincronizar
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-10"
            onClick={() => navigate("/components/new")}
          >
            <Plus className="size-4" />
            Nuevo
          </Button>
        </div>

        <section className="overflow-hidden rounded-md border border-border bg-white">
          {componentsQuery.isLoading ? (
            <div className="p-8 text-center text-sm text-text-secondary">Cargando…</div>
          ) : componentsQuery.isError ? (
            <div className="p-8 text-center text-sm text-destructive">
              No se pudo cargar el catálogo.
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-3 p-12 text-center">
              <p className="text-base font-medium text-text-primary">Aún no hay componentes</p>
              <p className="text-sm text-text-secondary">
                Ajusta los filtros o crea el primer componente.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30">
                  <TableHead className="w-12" />
                  <TableHead className="text-xs font-bold uppercase tracking-wide">SKU</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">MPN</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">
                    Nombre
                  </TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">
                    Familia
                  </TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">
                    Ubicación
                  </TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">
                    Supplier
                  </TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">
                    Precio (100u)
                  </TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">Stock</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wide">
                    <span className="inline-flex items-center gap-1">
                      NATO
                      <NatoScoreHelpPopover />
                    </span>
                  </TableHead>
                  <TableHead className="text-right text-xs font-bold uppercase tracking-wide">
                    Acciones
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((c) => (
                  <ComponentRow
                    key={c.id}
                    component={c}
                    supplierNameById={
                      new Map((suppliersQuery.data ?? []).map((s) => [s.id, s.name]))
                    }
                    onDelete={() => deleteMutation.mutateAsync(c.id)}
                    onView={() => navigate(`/components/${c.id}`)}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </section>

        {pageCount > 1 && (
          <DataTablePagination
            page={page}
            pageCount={pageCount}
            total={total}
            onPageChange={gotoPage}
          />
        )}
      </div>
    </DashboardLayout>
  );
}

interface ComponentRowProps {
  component: Component;
  supplierNameById: Map<string, string>;
  onDelete: () => Promise<void>;
  onView: () => void;
}

function ComponentRow({ component, supplierNameById, onDelete, onView }: ComponentRowProps) {
  const FamilyIcon = iconForFamily(component.family);
  const stockMin = effectiveStockMin(component);
  const supplierName = component.proveedor_preferente_id
    ? (supplierNameById.get(component.proveedor_preferente_id) ?? "—")
    : "—";
  return (
    <TableRow>
      <TableCell>
        <span
          aria-hidden
          className={cn(
            "inline-flex size-7 items-center justify-center rounded-md bg-brand/10 text-brand",
          )}
        >
          <FamilyIcon className="size-3.5" />
        </span>
      </TableCell>
      <TableCell className="font-medium text-text-primary">{component.sku ?? "—"}</TableCell>
      <TableCell className="font-mono text-xs text-text-secondary">{component.mpn}</TableCell>
      <TableCell className="text-text-primary">{component.name}</TableCell>
      <TableCell className="text-text-primary">{component.family}</TableCell>
      <TableCell className="font-mono text-xs text-text-primary">
        {component.location ?? "—"}
      </TableCell>
      <TableCell className="text-text-primary">{supplierName}</TableCell>
      <TableCell className="font-medium text-brand">
        {formatEuros(component.current_price_per_100_eur)}
      </TableCell>
      <TableCell>
        <StockStatusBadge stock={component.stock} stockMin={stockMin} supplierStock={[]} />
      </TableCell>
      <TableCell>
        <NatoScoreBadge value={component.nato_score} />
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            aria-label="Ver componente"
            onClick={onView}
          >
            <Eye className="size-4 text-text-secondary" />
          </Button>
          <ConfirmDeleteDialog
            trigger={
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7"
                aria-label="Eliminar componente"
              >
                <Trash2 className="size-4 text-red-600" />
              </Button>
            }
            onConfirm={onDelete}
          />
        </div>
      </TableCell>
    </TableRow>
  );
}
