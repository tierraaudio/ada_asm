import { MoreVertical, Plus, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatEuros } from "@/lib/format/currency";

import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { NatoScoreBadge } from "../components/NatoScoreBadge";
import { TierBadge } from "../components/TierBadge";
import {
  useDeleteComponent,
  useSyncComponent,
} from "../hooks/use-component-mutations";
import { useComponents } from "../hooks/use-components";
import { NATO_SCORE_VALUES, TIER_VALUES } from "../types";
import { NATO_SCORE_LABELS, TIER_LABELS } from "../rubrics";
import type { ComponentFilters, NatoScoreValue, TierValue } from "../types";

const PAGE_SIZE = 25;

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export function ComponentsListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const debouncedQ = useDebounced(searchInput);

  const family = searchParams.get("family") ?? undefined;
  const supplier = searchParams.get("supplier") ?? undefined;
  const tier = (searchParams.get("tier") ?? undefined) as TierValue | undefined;
  const natoScore = (searchParams.get("nato_score") ?? undefined) as
    | NatoScoreValue
    | undefined;
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const filters: ComponentFilters = useMemo(() => {
    const f: ComponentFilters = {};
    if (debouncedQ.trim()) f.q = debouncedQ.trim();
    if (family) f.family = family;
    if (supplier) f.supplier = supplier;
    if (tier) f.tier = tier;
    if (natoScore) f.nato_score = natoScore;
    return f;
  }, [debouncedQ, family, supplier, tier, natoScore]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (debouncedQ.trim()) next.set("q", debouncedQ.trim());
    else next.delete("q");
    if (page !== 1 && debouncedQ !== (searchParams.get("q") ?? "")) {
      next.delete("page");
    }
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ]);

  const { data, isLoading, isError } = useComponents({
    filters,
    page,
    pageSize: PAGE_SIZE,
  });
  const deleteMutation = useDeleteComponent();
  const syncMutation = useSyncComponent();

  function updateParam(key: string, value: string | undefined) {
    const next = new URLSearchParams(searchParams);
    if (value && value !== "__all__") next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setSearchParams(next, { replace: true });
  }

  function gotoPage(target: number) {
    const next = new URLSearchParams(searchParams);
    if (target <= 1) next.delete("page");
    else next.set("page", String(target));
    setSearchParams(next);
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-text-primary">Componentes</h1>
            <p className="text-sm text-text-secondary">
              Catálogo de componentes del taller. Búsqueda por MPN, SKU, nombre o
              familia.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                items[0] ? syncMutation.mutate(items[0].id) : undefined
              }
              disabled={items.length === 0 || syncMutation.isPending}
            >
              <RefreshCw className="size-4" /> Sincronizar
            </Button>
            <Button type="button" onClick={() => navigate("/components/new")}>
              <Plus className="size-4" /> Nuevo componente
            </Button>
          </div>
        </header>

        <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-white p-3">
          <label htmlFor="components-search" className="sr-only">
            Buscar componentes
          </label>
          <div className="relative flex-1 min-w-[16rem]">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-secondary" />
            <input
              id="components-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar por MPN, SKU, nombre o familia…"
              className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            />
          </div>
          <FilterDropdown
            label="Familia"
            value={family ?? "__all__"}
            options={[
              { value: "__all__", label: "Todas las familias" },
              { value: "Sensores", label: "Sensores" },
              { value: "Microcontroladores", label: "Microcontroladores" },
              { value: "Reguladores", label: "Reguladores" },
              { value: "Diodos", label: "Diodos" },
              { value: "Discretos", label: "Discretos" },
              { value: "Comunicaciones", label: "Comunicaciones" },
            ]}
            onChange={(v) => updateParam("family", v)}
          />
          <FilterDropdown
            label="Supplier"
            value={supplier ?? "__all__"}
            options={[
              { value: "__all__", label: "Todos los suppliers" },
              { value: "DigiKey", label: "DigiKey" },
              { value: "Mouser", label: "Mouser" },
              { value: "Farnell", label: "Farnell" },
              { value: "RS", label: "RS" },
            ]}
            onChange={(v) => updateParam("supplier", v)}
          />
          <FilterDropdown
            label="Tier"
            value={tier ?? "__all__"}
            options={[
              { value: "__all__", label: "Todos los tiers" },
              ...TIER_VALUES.map((t) => ({ value: t, label: TIER_LABELS[t] })),
            ]}
            onChange={(v) => updateParam("tier", v)}
          />
          <FilterDropdown
            label="NATO"
            value={natoScore ?? "__all__"}
            options={[
              { value: "__all__", label: "Todos los scorings" },
              ...NATO_SCORE_VALUES.map((s) => ({
                value: s,
                label: NATO_SCORE_LABELS[s],
              })),
            ]}
            onChange={(v) => updateParam("nato_score", v)}
          />
        </div>

        <section className="rounded-md border border-border bg-white">
          {isLoading ? (
            <div className="p-8 text-center text-sm text-text-secondary">Cargando…</div>
          ) : isError ? (
            <div className="p-8 text-center text-sm text-destructive">
              No se pudo cargar el catálogo.
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-3 p-12 text-center">
              <p className="text-base font-medium text-text-primary">
                Aún no hay componentes
              </p>
              <p className="text-sm text-text-secondary">
                Crea el primero para comenzar a gestionar tu catálogo.
              </p>
              <Button type="button" onClick={() => navigate("/components/new")}>
                <Plus className="size-4" /> Crea el primero
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>MPN</TableHead>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Familia</TableHead>
                  <TableHead>Ubicación</TableHead>
                  <TableHead>Supplier</TableHead>
                  <TableHead className="text-right">Precio (100u)</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead>Tier</TableHead>
                  <TableHead>NATO</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/components/${c.id}`)}
                  >
                    <TableCell className="font-mono text-xs">{c.mpn}</TableCell>
                    <TableCell>{c.name}</TableCell>
                    <TableCell>{c.family}</TableCell>
                    <TableCell>{c.location ?? "—"}</TableCell>
                    <TableCell>{c.supplier ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      {formatEuros(c.price_per_100)}
                    </TableCell>
                    <TableCell className="text-right">{c.stock}</TableCell>
                    <TableCell>
                      <TierBadge value={c.tier} />
                    </TableCell>
                    <TableCell>
                      <NatoScoreBadge value={c.nato_score} />
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <RowActions
                        componentId={c.id}
                        onDelete={() => deleteMutation.mutateAsync(c.id)}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>

        {pageCount > 1 && (
          <div className="flex items-center justify-end gap-3 text-sm text-text-secondary">
            <span>
              Página {page} de {pageCount} · {total} resultados
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => gotoPage(page - 1)}
              disabled={page <= 1}
            >
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => gotoPage(page + 1)}
              disabled={page >= pageCount}
            >
              Siguiente
            </Button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

interface FilterDropdownProps {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (next: string) => void;
}

function FilterDropdown({ label, value, options, onChange }: FilterDropdownProps) {
  const current =
    options.find((o) => o.value === value)?.label ??
    options.find((o) => o.value === "__all__")?.label ??
    label;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          {label}: {current}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        {options.map((opt) => (
          <DropdownMenuItem key={opt.value} onSelect={() => onChange(opt.value)}>
            {opt.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

interface RowActionsProps {
  componentId: string;
  onDelete: () => Promise<void>;
}

function RowActions({ componentId, onDelete }: RowActionsProps) {
  const navigate = useNavigate();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Acciones del componente"
        >
          <MoreVertical className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => navigate(`/components/${componentId}`)}>
          Ver
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => navigate(`/components/${componentId}/edit`)}
        >
          Editar
        </DropdownMenuItem>
        <ConfirmDeleteDialog
          trigger={
            <DropdownMenuItem
              destructive
              onSelect={(e) => e.preventDefault()}
            >
              Eliminar
            </DropdownMenuItem>
          }
          onConfirm={onDelete}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
