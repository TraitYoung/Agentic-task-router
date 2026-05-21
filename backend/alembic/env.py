"""Alembic migration environment.

No ORM is used in this project — migrations use raw SQL via alembic.op.
"""

import logging
from alembic import context
from sqlalchemy import engine_from_config, pool

logger = logging.getLogger("alembic.env")

# Alembic AutoMigrate cannot detect changes without a SQLAlchemy MetaData.
# We use raw SQL in migration scripts instead.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine,
    emits SQL as a script instead of executing it directly.
    """
    url = context.config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine from the config and associates a connection
    with the migration context.
    """
    connectable = engine_from_config(
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
