"""SQLAlchemy ORM models.

Importing this package wires every model into ``Base.metadata`` so Alembic
autogeneration can see the full schema in one place.
"""

from __future__ import annotations

from app.infrastructure.db.models.component import ComponentModel
from app.infrastructure.db.models.module import ModuleModel
from app.infrastructure.db.models.module_child import ModuleChildModel
from app.infrastructure.db.models.nato_scoring import ComponentNatoScoringModel
from app.infrastructure.db.models.password_reset_token import PasswordResetTokenModel
from app.infrastructure.db.models.refresh_token import RefreshTokenModel
from app.infrastructure.db.models.scoring_alternative import ScoringAlternativeModel
from app.infrastructure.db.models.scoring_classification import ScoringClassificationModel
from app.infrastructure.db.models.stock_event import StockEventModel
from app.infrastructure.db.models.supplier import SupplierModel
from app.infrastructure.db.models.supplier_price import SupplierPriceModel
from app.infrastructure.db.models.supplier_stock import SupplierStockModel
from app.infrastructure.db.models.user import UserModel

__all__ = [
    "ComponentModel",
    "ComponentNatoScoringModel",
    "ModuleChildModel",
    "ModuleModel",
    "PasswordResetTokenModel",
    "RefreshTokenModel",
    "ScoringAlternativeModel",
    "ScoringClassificationModel",
    "StockEventModel",
    "SupplierModel",
    "SupplierPriceModel",
    "SupplierStockModel",
    "UserModel",
]
