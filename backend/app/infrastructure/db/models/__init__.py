"""SQLAlchemy ORM models.

Importing this package wires every model into ``Base.metadata`` so Alembic
autogeneration can see the full schema in one place.
"""

from __future__ import annotations

from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.component_purchase import ComponentPurchaseModel
from app.infrastructure.db.models.password_reset_token import PasswordResetTokenModel
from app.infrastructure.db.models.refresh_token import RefreshTokenModel
from app.infrastructure.db.models.user import UserModel

__all__ = [
    "ComponentModel",
    "ComponentPurchaseModel",
    "PasswordResetTokenModel",
    "RefreshTokenModel",
    "UserModel",
]
