import type { NotificationFeed } from "../types";

/**
 * Placeholder notification feed.
 *
 * Strings come verbatim from Figma node 47:14343. The future "real feed" US
 * replaces the body of this hook with a TanStack Query call against the
 * backend; the components consuming this hook stay untouched.
 */
export function useNotifications(): NotificationFeed {
  const items = PLACEHOLDER_ITEMS;
  const unreadCount = items.reduce((acc, item) => acc + (item.read ? 0 : 1), 0);
  return { items, unreadCount };
}

const PLACEHOLDER_ITEMS: NotificationFeed["items"] = [
  {
    id: "1",
    title: "Juan Pérez ha añadido el componente STM32F407VGT6",
    subtitle: "Nuevo microcontrolador agregado al inventario",
    timestamp: "06/05/2026, 14:30",
    read: false,
  },
  {
    id: "2",
    title: "María García ha cerrado el proyecto Estación Meteorológica IoT",
    subtitle: "Proyecto marcado como completado",
    timestamp: "06/05/2026, 12:15",
    read: false,
  },
  {
    id: "3",
    title: "Precios diarios de componentes actualizados",
    subtitle: "Se han actualizado 247 precios de proveedores",
    timestamp: "06/05/2026, 09:00",
    read: true,
  },
  {
    id: "4",
    title: "Carlos López ha creado el proyecto Sistema IoT Industrial",
    subtitle: "Nuevo proyecto de monitorización industrial",
    timestamp: "05/05/2026, 16:45",
    read: true,
  },
  {
    id: "5",
    title: "Ana Martínez ha añadido el componente BME280",
    subtitle: "Sensor ambiental añadido al catálogo",
    timestamp: "05/05/2026, 14:20",
    read: true,
  },
  {
    id: "6",
    title: "Precios diarios de componentes actualizados",
    subtitle: "Se han actualizado 189 precios de proveedores",
    timestamp: "05/05/2026, 09:00",
    read: true,
  },
];
