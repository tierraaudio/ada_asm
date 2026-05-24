import { useState } from "react";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { HistoricoPreciosChart } from "@/features/shared/charts/HistoricoPreciosChart";
import type { Period } from "@/features/shared/charts/PeriodToggle";

import { useModulePriceHistory } from "../hooks/use-module-price-history";

interface ModulePriceHistoryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  moduleId: string;
  moduleName: string;
  moduleSku: string;
}

export function ModulePriceHistoryModal({
  open,
  onOpenChange,
  moduleId,
  moduleName,
  moduleSku,
}: ModulePriceHistoryModalProps) {
  const [period, setPeriod] = useState<Period>("year");
  const query = useModulePriceHistory(moduleId, period, open);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[min(95vw,1100px)] max-w-none overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">
            Histórico de precios —{" "}
            <span className="font-mono text-text-secondary">{moduleSku}</span>{" "}
            <span className="text-text-secondary">·</span> {moduleName}
          </DialogTitle>
        </DialogHeader>

        <section className="h-[420px] rounded-lg border border-border p-4">
          {query.isLoading ? (
            <p className="flex h-full items-center justify-center text-sm text-text-secondary">
              Cargando histórico…
            </p>
          ) : (
            <HistoricoPreciosChart
              mode="module-aggregate"
              series={query.data?.series ?? []}
              period={period}
              onPeriodChange={setPeriod}
            />
          )}
        </section>
      </DialogContent>
    </Dialog>
  );
}
