import { z } from "zod";

import { NATO_SCORE_VALUES, TIER_VALUES } from "./types";

const optionalString = z
  .string()
  .trim()
  .max(200)
  .transform((v) => (v === "" ? undefined : v))
  .optional();

const optionalShortString = z
  .string()
  .trim()
  .max(100)
  .transform((v) => (v === "" ? undefined : v))
  .optional();

const optionalUrl = z
  .union([
    z.literal(""),
    z.string().trim().url("Debe ser una URL válida"),
  ])
  .transform((v) => (v === "" ? undefined : v))
  .optional();

const optionalPrice = z
  .union([z.string().trim(), z.number()])
  .transform((value) => (value === "" ? undefined : value))
  .refine((value) => value === undefined || !Number.isNaN(Number(value)), {
    message: "Debe ser un número válido",
  })
  .refine((value) => value === undefined || Number(value) >= 0, {
    message: "Debe ser mayor o igual a 0",
  })
  .optional();

const optionalCountry = z
  .union([
    z.literal(""),
    z.string().trim().regex(/^[A-Z]{2}$/, "ISO 3166-1 alpha-2 (2 letras mayúsculas)"),
  ])
  .transform((v) => (v === "" ? undefined : v))
  .optional();

export const componentCreateSchema = z.object({
  mpn: z.string().trim().min(1, "Requerido").max(100),
  name: z.string().trim().min(1, "Requerido").max(200),
  family: z.string().trim().min(1, "Requerido").max(100),
  tier: z.enum(TIER_VALUES),
  nato_score: z.enum(NATO_SCORE_VALUES),
  sku: optionalShortString,
  description: optionalString,
  datasheet_url: optionalUrl,
  location: optionalShortString,
  supplier: optionalShortString,
  price_per_100: optionalPrice,
  stock: z.coerce.number().int().nonnegative().default(0),
  country_of_origin: optionalCountry,
});

export type ComponentCreateInput = z.input<typeof componentCreateSchema>;
export type ComponentCreatePayload = z.output<typeof componentCreateSchema>;

export const componentUpdateSchema = componentCreateSchema
  .omit({ mpn: true })
  .partial();

export type ComponentUpdateInput = z.input<typeof componentUpdateSchema>;
export type ComponentUpdatePayload = z.output<typeof componentUpdateSchema>;
