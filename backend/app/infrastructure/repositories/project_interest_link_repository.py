"""SQLAlchemy implementation of the project interest links sub-entity repo."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.project_interest_link import ProjectInterestLink
from app.infrastructure.db.models.project_interest_link import ProjectInterestLinkModel


def _to_entity(row: ProjectInterestLinkModel) -> ProjectInterestLink:
    return ProjectInterestLink(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        url=row.url,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyProjectInterestLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_project(self, project_id: UUID) -> list[ProjectInterestLink]:
        rows = (
            (
                await self._session.execute(
                    select(ProjectInterestLinkModel)
                    .where(ProjectInterestLinkModel.project_id == project_id)
                    .order_by(
                        ProjectInterestLinkModel.sort_order,
                        ProjectInterestLinkModel.created_at,
                    )
                )
            )
            .scalars()
            .all()
        )
        return [_to_entity(r) for r in rows]

    async def get(self, link_id: UUID) -> ProjectInterestLink | None:
        row = (
            await self._session.execute(
                select(ProjectInterestLinkModel).where(
                    ProjectInterestLinkModel.id == link_id
                )
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, link: ProjectInterestLink) -> ProjectInterestLink:
        row = ProjectInterestLinkModel(
            id=link.id,
            project_id=link.project_id,
            name=link.name,
            url=link.url,
            sort_order=link.sort_order,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def update(self, link: ProjectInterestLink) -> ProjectInterestLink:
        row = (
            await self._session.execute(
                select(ProjectInterestLinkModel).where(
                    ProjectInterestLinkModel.id == link.id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"project_interest_link {link.id} disappeared mid-update")
        row.name = link.name
        row.url = link.url
        row.sort_order = link.sort_order
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row)

    async def delete(self, link_id: UUID) -> bool:
        result = await self._session.execute(
            delete(ProjectInterestLinkModel).where(
                ProjectInterestLinkModel.id == link_id
            )
        )
        await self._session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0
