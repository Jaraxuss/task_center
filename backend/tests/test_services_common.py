"""Unit tests for services.common helpers."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Customer
from services.common import get_or_404


def test_get_or_404_returns_entity(db_session: Session) -> None:
    customer = Customer(name="Acme", aliases_json="[]", tags_json="[]")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    found = get_or_404(db_session, Customer, customer.id)
    assert found.id == customer.id
    assert found.name == "Acme"


def test_get_or_404_raises_404_default_label(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        get_or_404(db_session, Customer, 999_999)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Customer not found"


def test_get_or_404_raises_404_with_custom_name(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        get_or_404(db_session, Customer, 999_999, name="Review batch")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Review batch not found"
