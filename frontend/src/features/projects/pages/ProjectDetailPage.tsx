import { Edit3, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { ConfirmDeleteDialog } from "@/features/components/components/ConfirmDeleteDialog";
import { ModulesHierarchyTable } from "@/features/modules/components/ModulesHierarchyTable";
import { useDetailNavPush } from "@/features/shared/nav/DetailNavControls";
import { DetailPageHeader } from "@/features/shared/nav/DetailPageHeader";
import { useDetailNavStack } from "@/features/shared/nav/DetailNavStack";

import { ProjectHeaderCard } from "../components/ProjectHeaderCard";
import { useProjectDetail } from "../hooks/use-project-detail";
import {
  useAddInterestLink,
  useDeleteProject,
  useRemoveInterestLink,
  useUpdateInterestLink,
} from "../hooks/use-project-mutations";

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const query = useProjectDetail(id);
  const deleteMutation = useDeleteProject();
  const addInterestLink = useAddInterestLink();
  const updateInterestLink = useUpdateInterestLink();
  const removeInterestLink = useRemoveInterestLink();
  const { reset: resetNavStack } = useDetailNavStack();
  useDetailNavPush();

  if (!id || query.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando proyecto…</p>
      </DashboardLayout>
    );
  }
  if (query.isError || !query.data) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el proyecto.</p>
      </DashboardLayout>
    );
  }
  const project = query.data;

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-6">
        <DetailPageHeader
          closeTo="/projects"
          rightSlot={
            <>
              <ConfirmDeleteDialog
                trigger={
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-label="Archivar proyecto"
                  >
                    <Trash2 className="size-4 text-red-600" />
                    Archivar
                  </Button>
                }
                title={`¿Archivar el proyecto «${project.name}»?`}
                description="El proyecto pasa a estado «Archivado» y desaparece de las listas por defecto. Se puede recuperar editando el estado más adelante."
                confirmLabel="Archivar"
                onConfirm={async () => {
                  await deleteMutation.mutateAsync(project.id);
                  resetNavStack();
                  navigate("/projects");
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => navigate(`/projects/${project.id}/edit`)}
              >
                <Edit3 className="size-4" />
                Editar Proyecto
              </Button>
            </>
          }
        />

        <ProjectHeaderCard
          project={project}
          onAddInterestLink={async (payload) => {
            await addInterestLink.mutateAsync({
              id: project.id,
              payload: {
                name: payload.name,
                url: payload.url,
                sort_order: project.interest_links.length,
              },
            });
          }}
          onEditInterestLink={async (linkId, payload) => {
            await updateInterestLink.mutateAsync({
              id: project.id,
              linkId,
              payload,
            });
          }}
          onRemoveInterestLink={async (linkId) => {
            await removeInterestLink.mutateAsync({
              id: project.id,
              linkId,
            });
          }}
        />

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Contiene
          </h2>
          <ModulesHierarchyTable
            directChildren={project.children}
            expandable
            emptyMessage="Este proyecto no contiene módulos ni componentes."
          />
        </section>
      </div>
    </DashboardLayout>
  );
}
