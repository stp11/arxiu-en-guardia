from alembic import command


def test_models_match_migrations(alembic_config):
    # Same as `alembic check`: fails if a model changed without a migration.
    command.check(alembic_config)
