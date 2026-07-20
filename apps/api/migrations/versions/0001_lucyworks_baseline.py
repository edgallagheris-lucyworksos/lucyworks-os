"""LucyWorks schema baseline.

Revision ID: 0001_lucyworks_baseline
Revises: None
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel

import app as app_package

revision: str = "0001_lucyworks_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _register_models() -> None:
    for module in pkgutil.iter_modules(app_package.__path__):
        if module.name == "models" or module.name.endswith("_models"):
            importlib.import_module(f"app.{module.name}")


def upgrade() -> None:
    _register_models()
    SQLModel.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    _register_models()
    SQLModel.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
