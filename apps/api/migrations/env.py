from __future__ import annotations

import importlib
import os
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.database import _normalise_database_url
import app as app_package

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def import_model_modules() -> None:
    for module in pkgutil.iter_modules(app_package.__path__):
        if module.name == "models" or module.name.endswith("_models"):
            importlib.import_module(f"app.{module.name}")


import_model_modules()
target_metadata = SQLModel.metadata


def database_url() -> str:
    return _normalise_database_url(os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url")))


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
