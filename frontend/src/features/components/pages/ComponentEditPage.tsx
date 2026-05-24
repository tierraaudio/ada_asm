import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { Calendar, MapPin, Package, Save, X } from "lucide-react";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils/cn";

import type { ComponentCreatePayload, ComponentUpdatePayload } from "../api/components-api";
import { HistoricoPreciosChart } from "@/features/shared/charts/HistoricoPreciosChart";
import { PreciosDeHoyTable } from "../components/PreciosDeHoyTable";
import { StockDisponibleChart } from "../components/StockDisponibleChart";
import { FAMILY_VALUES, TIPO_ALMACENAMIENTO_VALUES } from "../types";
import { useComponentDetail } from "../hooks/use-component-detail";
import { useCreateComponent, useUpdateComponent } from "../hooks/use-component-mutations";
import { useStockEvents, useSupplierPrices, useSupplierStocks } from "../hooks/use-supplier-data";
import { useSuppliers } from "../hooks/use-suppliers";

interface ComponentEditPageProps {
  mode: "create" | "edit";
}

const formSchema = z.object({
  mpn: z.string().trim().min(1, "MPN obligatorio").max(100),
  sku: z.string().trim().max(100).optional(),
  name: z.string().trim().min(1, "Nombre obligatorio").max(200),
  description: z.string().optional(),
  datasheet_url: z
    .string()
    .trim()
    .optional()
    .refine(
      (v) => !v || /^https?:\/\//i.test(v),
      "URL inválida (debe empezar por http:// o https://)",
    ),
  location: z.string().trim().max(100).optional(),
  tipo_almacenamiento: z
    .string()
    .optional()
    .refine(
      (v) => !v || (TIPO_ALMACENAMIENTO_VALUES as readonly string[]).includes(v),
      "Valor inválido",
    ),
  family: z
    .string()
    .min(1, "Familia obligatoria")
    .refine((v) => (FAMILY_VALUES as readonly string[]).includes(v), "Familia inválida"),
  proveedor_preferente_id: z.string().optional(),
  fabricante: z.string().trim().max(120).optional(),
  stock: z.coerce.number().int().min(0, "Stock no puede ser negativo"),
  holded_id: z.string().trim().max(80).optional(),
});

type FormValues = z.infer<typeof formSchema>;

const EMPTY_DEFAULTS: FormValues = {
  mpn: "",
  sku: "",
  name: "",
  description: "",
  datasheet_url: "",
  location: "",
  tipo_almacenamiento: "",
  family: "",
  proveedor_preferente_id: "",
  fabricante: "",
  stock: 0,
  holded_id: "",
};

function formatDdMmYyyy(iso: string | null | undefined): string {
  if (!iso) return "—";
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

export function ComponentEditPage({ mode }: ComponentEditPageProps) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = mode === "edit";

  const detailQuery = useComponentDetail(isEdit ? id : undefined);
  const suppliersQuery = useSuppliers();
  const pricesQuery = useSupplierPrices(isEdit ? id : undefined);
  const stocksQuery = useSupplierStocks(isEdit ? id : undefined);
  // Pre-fetch even if we don't render the chart; the detail page will hit the
  // same cache when the user navigates back.
  useStockEvents(isEdit ? id : undefined);

  const create = useCreateComponent();
  const update = useUpdateComponent();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: EMPTY_DEFAULTS,
  });

  // Hydrate the form when the detail loads (edit mode only).
  useEffect(() => {
    if (!isEdit || !detailQuery.data) return;
    const c = detailQuery.data;
    reset({
      mpn: c.mpn,
      sku: c.sku ?? "",
      name: c.name,
      description: c.description ?? "",
      datasheet_url: c.datasheet_url ?? "",
      location: c.location ?? "",
      tipo_almacenamiento: c.tipo_almacenamiento ?? "",
      family: c.family,
      proveedor_preferente_id: c.proveedor_preferente_id ?? "",
      fabricante: c.fabricante ?? "",
      stock: c.stock,
      holded_id: c.holded_id ?? "",
    });
  }, [isEdit, detailQuery.data, reset]);

  const onCancel = () => {
    if (isEdit && id) {
      navigate(`/components/${id}`);
    } else {
      navigate("/components");
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    const payload = {
      sku: values.sku?.trim() ? values.sku.trim() : null,
      name: values.name.trim(),
      description: values.description?.trim() ? values.description.trim() : null,
      datasheet_url: values.datasheet_url?.trim() ? values.datasheet_url.trim() : null,
      location: values.location?.trim() ? values.location.trim() : null,
      tipo_almacenamiento: values.tipo_almacenamiento?.trim()
        ? values.tipo_almacenamiento.trim()
        : null,
      family: values.family.trim(),
      proveedor_preferente_id: values.proveedor_preferente_id
        ? values.proveedor_preferente_id
        : null,
      fabricante: values.fabricante?.trim() ? values.fabricante.trim() : null,
      stock: values.stock,
      holded_id: values.holded_id?.trim() ? values.holded_id.trim() : null,
    };

    try {
      if (isEdit && id) {
        await update.mutateAsync({ id, payload: payload as ComponentUpdatePayload });
        navigate(`/components/${id}`);
      } else {
        // Sensible defaults for fields not exposed in the Figma form — the
        // user reclassifies the component via the NATO scoring flow afterwards.
        const createPayload: ComponentCreatePayload = {
          ...payload,
          mpn: values.mpn.trim(),
          tier: 4,
          nato_score: "C",
        };
        const created = await create.mutateAsync(createPayload);
        navigate(`/components/${created.id}`);
      }
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409) {
        // Surface MPN duplicate on the mpn field.
        setValue("mpn", values.mpn, { shouldValidate: true });
      }
    }
  });

  const submitError =
    create.error && isAxiosError(create.error) && create.error.response?.status === 409
      ? "Ya existe un componente con ese MPN."
      : update.error
        ? "No se pudo guardar. Inténtalo de nuevo."
        : null;

  if (isEdit && id && detailQuery.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando componente…</p>
      </DashboardLayout>
    );
  }

  if (isEdit && (detailQuery.isError || (id && !detailQuery.data))) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el componente.</p>
      </DashboardLayout>
    );
  }

  const component = detailQuery.data;
  const suppliers = suppliersQuery.data ?? [];
  const prices = pricesQuery.data ?? [];
  const stocks = stocksQuery.data ?? [];

  return (
    <DashboardLayout>
      <form
        noValidate
        onSubmit={onSubmit}
        className="mx-auto flex w-full max-w-[1920px] flex-col gap-6"
        aria-label={isEdit ? "Editar componente" : "Nuevo componente"}
      >
        <header className="flex items-center justify-between">
          <button
            type="button"
            aria-label="Cerrar"
            onClick={onCancel}
            className="inline-flex size-9 items-center justify-center rounded-md text-text-secondary hover:bg-muted hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            <X className="size-5" />
          </button>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onCancel}>
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={isSubmitting || (isEdit && !isDirty)}>
              <Save className="size-4" />
              {isEdit ? "Guardar cambios" : "Crear componente"}
            </Button>
          </div>
        </header>

        {submitError && (
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
          >
            {submitError}
          </div>
        )}

        <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
          {/* Row 1: MPN + SKU */}
          <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
            <FormField
              label="MPN (Manufacture Part Number)"
              error={errors.mpn?.message}
              hint={isEdit ? "Identificador del fabricante — no editable." : undefined}
            >
              <input
                {...register("mpn")}
                type="text"
                readOnly={isEdit}
                disabled={isEdit}
                className={cn(inputCls, isEdit && "bg-muted/40 text-text-secondary")}
                placeholder="STM32F407VGT6"
              />
            </FormField>
            <FormField label="SKU" error={errors.sku?.message}>
              <input {...register("sku")} type="text" className={inputCls} placeholder="MCU-001" />
            </FormField>
          </div>

          {/* Row 2: Nombre */}
          <div className="mt-4">
            <FormField label="Nombre" error={errors.name?.message}>
              <input
                {...register("name")}
                type="text"
                className={inputCls}
                placeholder="STM32F407VGT6 - ARM Cortex-M4 MCU"
              />
            </FormField>
          </div>

          {/* Row 3: Descripción */}
          <div className="mt-4">
            <FormField label="Descripción" error={errors.description?.message}>
              <textarea
                {...register("description")}
                rows={3}
                className={cn(inputCls, "min-h-[80px] resize-y")}
              />
            </FormField>
          </div>

          {/* Row 4: Datasheet URL */}
          <div className="mt-4">
            <FormField label="Datasheet URL" error={errors.datasheet_url?.message}>
              <input
                {...register("datasheet_url")}
                type="url"
                className={cn(inputCls, "font-mono text-xs")}
                placeholder="https://www.st.com/resource/en/datasheet/stm32f407vg.pdf"
              />
            </FormField>
          </div>

          {/* Row 5: Audit strip — only in edit mode */}
          {isEdit && component && (
            <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-border pt-4 md:grid-cols-4">
              <ReadonlyField
                icon={<Calendar className="size-3.5" />}
                label="Fecha de creación"
                value={formatDdMmYyyy(component.fecha_creacion)}
              />
              <ReadonlyField
                icon={<Calendar className="size-3.5" />}
                label="Última modificación"
                value={formatDdMmYyyy(component.updated_at)}
              />
            </div>
          )}

          {/* Row 6: Ubicación + Tipo almacenamiento + Familia + Proveedor */}
          <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2 lg:grid-cols-4">
            <FormField
              label="Ubicación"
              icon={<MapPin className="size-3.5" />}
              error={errors.location?.message}
            >
              <input
                {...register("location")}
                type="text"
                className={inputCls}
                placeholder="G-A-12"
              />
            </FormField>
            <FormField
              label="Tipo almacenamiento"
              icon={<Package className="size-3.5" />}
              error={errors.tipo_almacenamiento?.message}
            >
              <Controller
                control={control}
                name="tipo_almacenamiento"
                render={({ field }) => (
                  <Select
                    value={field.value ? field.value : "__none__"}
                    onValueChange={(v) => field.onChange(v === "__none__" ? "" : v)}
                  >
                    <SelectTrigger className={inputCls}>
                      <SelectValue placeholder="Selecciona…" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">—</SelectItem>
                      {TIPO_ALMACENAMIENTO_VALUES.map((v) => (
                        <SelectItem key={v} value={v}>
                          {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FormField>
            <FormField
              label="Familia"
              icon={<Package className="size-3.5" />}
              error={errors.family?.message}
            >
              <Controller
                control={control}
                name="family"
                render={({ field }) => (
                  <Select
                    {...(field.value ? { value: field.value } : {})}
                    onValueChange={(v) => field.onChange(v)}
                  >
                    <SelectTrigger className={inputCls}>
                      <SelectValue placeholder="Selecciona familia…" />
                    </SelectTrigger>
                    <SelectContent>
                      {FAMILY_VALUES.map((v) => (
                        <SelectItem key={v} value={v}>
                          {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FormField>
            <FormField label="Proveedor preferente">
              <Controller
                control={control}
                name="proveedor_preferente_id"
                render={({ field }) => (
                  <Select
                    value={field.value ? field.value : "__none__"}
                    onValueChange={(v) => field.onChange(v === "__none__" ? "" : v)}
                  >
                    <SelectTrigger className={inputCls}>
                      <SelectValue placeholder="Sin proveedor preferente" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— Sin proveedor —</SelectItem>
                      {suppliers.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FormField>
          </div>

          {/* Row 7: Fabricante + Stock + Holded ID */}
          <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-3">
            <FormField label="Fabricante" error={errors.fabricante?.message}>
              <input
                {...register("fabricante")}
                type="text"
                className={inputCls}
                placeholder="STMicroelectronics"
              />
            </FormField>
            <FormField label="Stock" error={errors.stock?.message}>
              <input
                {...register("stock")}
                type="number"
                min={0}
                className={inputCls}
                placeholder="0"
              />
            </FormField>
            <FormField label="Holded ID" error={errors.holded_id?.message}>
              <input
                {...register("holded_id")}
                type="text"
                className={inputCls}
                placeholder="HLD-2024-001"
              />
            </FormField>
          </div>
        </section>

        {/* Reference panels — read-only context from the detail, only in edit. */}
        {isEdit && component && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.3fr_1.3fr]">
            <RefSection title="Precios de hoy">
              {pricesQuery.isLoading ? (
                <p className="text-sm text-text-secondary">Cargando precios…</p>
              ) : (
                <PreciosDeHoyTable
                  prices={prices}
                  suppliers={suppliers}
                  preferredSupplierId={component.proveedor_preferente_id}
                />
              )}
            </RefSection>
            <RefSection title="Histórico de precios">
              {pricesQuery.isLoading ? (
                <p className="text-sm text-text-secondary">Cargando histórico…</p>
              ) : (
                <HistoricoPreciosChart prices={prices} suppliers={suppliers} />
              )}
            </RefSection>
            <RefSection title="Stock disponible en proveedores">
              {stocksQuery.isLoading ? (
                <p className="text-sm text-text-secondary">Cargando stock…</p>
              ) : (
                <StockDisponibleChart snapshots={stocks} suppliers={suppliers} />
              )}
            </RefSection>
          </div>
        )}
      </form>
    </DashboardLayout>
  );
}

const inputCls =
  "h-10 w-full rounded-md border border-border bg-white px-3 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";

interface FormFieldProps {
  label: string;
  icon?: React.ReactNode | undefined;
  error?: string | undefined;
  hint?: string | undefined;
  children: React.ReactNode;
}

function FormField({ label, icon, error, hint, children }: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
        {icon && <span className="text-text-secondary">{icon}</span>}
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-text-secondary">{hint}</p>}
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function ReadonlyField({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-text-secondary">
        {icon && <span className="text-text-secondary/70">{icon}</span>}
        {label}
      </span>
      <span className="text-sm font-medium text-text-primary">{value}</span>
    </div>
  );
}

function RefSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex h-[480px] flex-col rounded-lg border border-border bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
        {title}
      </h3>
      <div className="flex-1 overflow-hidden">{children}</div>
    </section>
  );
}
