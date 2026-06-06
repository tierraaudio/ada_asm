"""Supplier integrations.

Each module under this package implements `SupplierAdapter` for one
distributor (Mouser, DigiKey, TME, Farnell, RS). The `registry` module is
the single place where the application decides which adapters are active
based on settings (credentials present + supplier code listed in
`SUPPLIER_SYNC_ENABLED_SUPPLIERS`).
"""

from __future__ import annotations
