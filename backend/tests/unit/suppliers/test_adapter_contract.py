"""Cross-adapter contract test.

Parameterised over every concrete `SupplierAdapter` so the same
behavioural guarantees are enforced on all of them as the codebase
grows:

- Implements the runtime-checkable `SupplierAdapter` Protocol.
- Exposes a `code` attribute matching the supplier's identifier in
  `SUPPLIER_CODES`.
- Has a callable async `fetch_by_mpn(mpn: str) -> SupplierQuote | None`.

The test imports each adapter via its module path and instantiates with
dummy credentials so we never hit the network. We intentionally do NOT
call `fetch_by_mpn` here — that's covered by the per-adapter test files
with respx-mocked HTTP. This file's job is the **interface contract**.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from app.domain.entities.supplier_quote import SupplierQuote
from app.domain.repositories.supplier_adapter import SupplierAdapter


_ADAPTER_CASES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "mouser",
        "app.infrastructure.suppliers.mouser:MouserAdapter",
        {"api_key": "dummy"},
    ),
    (
        "digikey",
        "app.infrastructure.suppliers.digikey:DigiKeyAdapter",
        {
            "client_id": "dummy",
            "client_secret": "dummy",
            "token_url": "https://api.digikey.com/v1/oauth2/token",
        },
    ),
    (
        "tme",
        "app.infrastructure.suppliers.tme:TmeAdapter",
        {"token": "x" * 50, "app_secret": "y" * 20},
    ),
    (
        "farnell",
        "app.infrastructure.suppliers.farnell:FarnellAdapter",
        {"api_key": "dummy", "store_id": "es.farnell.com"},
    ),
    (
        "rs",
        "app.infrastructure.suppliers.rs:RsAdapter",
        {"api_key": "dummy"},
    ),
]


def _import_class(path: str) -> type[object]:
    module_path, _, class_name = path.partition(":")
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


@pytest.mark.parametrize(
    ("expected_code", "import_path", "ctor_kwargs"),
    _ADAPTER_CASES,
    ids=[c[0] for c in _ADAPTER_CASES],
)
def test_adapter_implements_protocol_and_exposes_code(
    expected_code: str,
    import_path: str,
    ctor_kwargs: dict[str, Any],
) -> None:
    cls = _import_class(import_path)
    instance = cls(**ctor_kwargs)

    # Runtime-checkable Protocol — `isinstance` verifies all members are
    # present and callable.
    assert isinstance(instance, SupplierAdapter), (
        f"{cls.__name__} does not satisfy SupplierAdapter Protocol"
    )

    assert instance.code == expected_code, (
        f"{cls.__name__}.code = {instance.code!r}, expected {expected_code!r}"
    )


@pytest.mark.parametrize(
    ("import_path", "ctor_kwargs"),
    [(c[1], c[2]) for c in _ADAPTER_CASES],
    ids=[c[0] for c in _ADAPTER_CASES],
)
def test_fetch_by_mpn_is_async_with_correct_signature(
    import_path: str,
    ctor_kwargs: dict[str, Any],
) -> None:
    cls = _import_class(import_path)
    instance = cls(**ctor_kwargs)

    fn = instance.fetch_by_mpn
    assert inspect.iscoroutinefunction(fn), (
        f"{cls.__name__}.fetch_by_mpn must be `async def`"
    )

    sig = inspect.signature(fn)
    # Exactly one explicit parameter: `mpn`.
    params = [p for p in sig.parameters.values() if p.name != "self"]
    assert len(params) == 1, (
        f"{cls.__name__}.fetch_by_mpn takes {len(params)} params, expected 1"
    )
    assert params[0].name == "mpn"

    # Return annotation should reference SupplierQuote — accept the union
    # `SupplierQuote | None` as a forward ref or eager evaluation. We
    # match against the qualified name to stay robust to future imports.
    return_text = str(sig.return_annotation)
    assert "SupplierQuote" in return_text, (
        f"{cls.__name__}.fetch_by_mpn return type missing SupplierQuote: {return_text}"
    )
    assert "None" in return_text, (
        f"{cls.__name__}.fetch_by_mpn return type missing None: {return_text}"
    )


def test_every_known_supplier_has_a_concrete_adapter() -> None:
    """If we add a new supplier code to SupplierQuote.SupplierCode without
    adding an adapter here, this test fails and forces the maintainer to
    extend the contract suite."""
    from app.domain.entities.supplier_quote import SupplierCode

    known = set(SupplierCode.__args__)  # type: ignore[attr-defined]
    covered = {case[0] for case in _ADAPTER_CASES}
    missing = known - covered
    assert missing == set(), (
        f"Supplier codes {missing} declared in SupplierCode but absent from "
        f"the contract test suite (_ADAPTER_CASES)"
    )


def test_supplierquote_is_importable() -> None:
    # Smoke test: keep the public domain contract reachable so the
    # contract test doesn't pass while the domain layer drifts.
    assert SupplierQuote is not None
