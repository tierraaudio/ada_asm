import { useParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";

import { ComponentDetailTabs } from "../components/ComponentDetailTabs";
import { ComponentHeaderCard } from "../components/ComponentHeaderCard";
import { NatoScoreBadge } from "../components/NatoScoreBadge";
import { NatoScoreHelpPopover } from "../components/NatoScoreHelpPopover";
import { TierBadge } from "../components/TierBadge";
import { useComponent } from "../hooks/use-component";
import {
  NATO_SCORE_DESCRIPTIONS,
  NATO_SCORE_LABELS,
  TIER_DESCRIPTIONS,
  TIER_LABELS,
} from "../rubrics";
import { NATO_SCORE_VALUES, TIER_VALUES } from "../types";

export function ComponentNatoScoringPage() {
  const { id } = useParams<{ id: string }>();
  const componentQuery = useComponent(id);

  if (!id || componentQuery.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando componente…</p>
      </DashboardLayout>
    );
  }
  if (!componentQuery.data) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el componente.</p>
      </DashboardLayout>
    );
  }

  const component = componentQuery.data;

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <ComponentHeaderCard component={component} />
        <ComponentDetailTabs componentId={id} />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Tier
            </h2>
            <div className="mb-4 flex items-center gap-3">
              <TierBadge value={component.tier} className="text-base" />
              <span className="text-base font-medium text-text-primary">
                Tier {TIER_LABELS[component.tier]}
              </span>
            </div>
            <p className="text-sm text-text-secondary">
              {TIER_DESCRIPTIONS[component.tier]}
            </p>
          </section>

          <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
                Scoring OTAN
              </h2>
              <NatoScoreHelpPopover />
            </div>
            <div className="mb-4 flex items-center gap-3">
              <NatoScoreBadge value={component.nato_score} className="text-base" />
              <span className="text-base font-medium text-text-primary">
                {NATO_SCORE_LABELS[component.nato_score]}
              </span>
            </div>
            <p className="mb-4 text-sm text-text-secondary">
              {NATO_SCORE_DESCRIPTIONS[component.nato_score]}
            </p>
            <dl className="grid grid-cols-[8rem_1fr] gap-y-1 text-sm">
              <dt className="text-text-secondary">País de origen</dt>
              <dd className="font-medium">{component.country_of_origin ?? "—"}</dd>
            </dl>
          </section>
        </div>

        <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Leyenda
          </h2>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold">Tiers</h3>
              <dl className="space-y-2">
                {TIER_VALUES.map((tier) => (
                  <div key={tier} className="grid grid-cols-[4rem_1fr] items-baseline gap-3">
                    <dt>
                      <TierBadge value={tier} />
                    </dt>
                    <dd className="text-xs text-text-secondary">
                      {TIER_DESCRIPTIONS[tier]}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">Scoring OTAN</h3>
              <dl className="space-y-2">
                {NATO_SCORE_VALUES.map((score) => (
                  <div
                    key={score}
                    className="grid grid-cols-[7rem_1fr] items-baseline gap-3"
                  >
                    <dt>
                      <NatoScoreBadge value={score} />
                    </dt>
                    <dd className="text-xs text-text-secondary">
                      {NATO_SCORE_DESCRIPTIONS[score]}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}
