"""Unit tests for Migration API public interface."""

from __future__ import annotations

from pathlib import Path


class TestMigrationImports:
    """Test that all migration components can be imported."""

    def test_migration_runner_import(self):
        """MigrationRunner can be imported from migrations module."""
        from py_accountant.infrastructure.migrations import MigrationRunner

        assert MigrationRunner is not None
        assert hasattr(MigrationRunner, "upgrade_to_head")

    def test_include_in_alembic_import(self):
        """include_in_alembic can be imported from migrations module."""
        from py_accountant.infrastructure.migrations import include_in_alembic

        assert include_in_alembic is not None
        assert callable(include_in_alembic)

    def test_errors_import(self):
        """Migration errors can be imported from migrations module."""
        from py_accountant.infrastructure.migrations import (
            MigrationError,
            VersionMismatchError,
        )

        assert issubclass(VersionMismatchError, MigrationError)
        assert issubclass(MigrationError, Exception)


class TestVersionSchema:
    """Test __version_schema__ constant."""

    def test_version_schema_exists(self):
        """__version_schema__ is defined in package root."""
        from py_accountant import __version_schema__

        assert __version_schema__ is not None
        assert isinstance(__version_schema__, str)

    def test_version_schema_format(self):
        """__version_schema__ has correct format (NNNN_description)."""
        from py_accountant import __version_schema__

        # Should match pattern: 0001_name or 0008_add_account_aggregates
        assert len(__version_schema__) > 0
        assert "_" in __version_schema__

        # Should start with 4 digits
        parts = __version_schema__.split("_", 1)
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert len(parts[0]) == 4

    def test_version_schema_matches_latest_migration(self):
        """__version_schema__ matches the latest migration file."""
        from py_accountant import __version_schema__

        # Get migrations directory
        migrations_dir = (
            Path(__file__).parent.parent.parent.parent.parent
            / "alembic"
            / "versions"
        )

        # Get all migration files
        migration_files = sorted(
            [f.stem for f in migrations_dir.glob("0*.py") if f.is_file()]
        )

        # Latest migration should match __version_schema__
        if migration_files:
            latest_migration = migration_files[-1]
            assert __version_schema__ == latest_migration, (
                f"__version_schema__ ({__version_schema__}) "
                f"doesn't match latest migration ({latest_migration})"
            )


class TestBackwardCompatibility:
    """Test backward compatibility of public API."""

    def test_migrations_module_exports(self):
        """migrations module exports all expected components."""
        from py_accountant.infrastructure import migrations

        expected_exports = [
            "MigrationRunner",
            "include_in_alembic",
            "MigrationError",
            "VersionMismatchError",
        ]

        for export in expected_exports:
            assert hasattr(migrations, export), f"Missing export: {export}"

    def test_no_circular_imports(self):
        """Importing py_accountant doesn't cause circular imports."""
        # This test simply imports and checks no ImportError
        import py_accountant
        from py_accountant.infrastructure.migrations import MigrationRunner

        assert py_accountant is not None
        assert MigrationRunner is not None


class TestIntegration:
    """Test integration between components."""

    def test_migration_runner_instantiation(self):
        """MigrationRunner can be instantiated with Engine."""
        from sqlalchemy import create_engine

        from py_accountant.infrastructure.migrations import MigrationRunner

        engine = create_engine("sqlite:///:memory:")
        runner = MigrationRunner(engine)
        assert runner is not None
        # Don't test actual functionality here (covered in test_runner.py)

    def test_version_schema_accessible_from_runner(self):
        """__version_schema__ is accessible and can be used with MigrationRunner."""
        from py_accountant import __version_schema__
        from py_accountant.infrastructure.migrations import MigrationRunner

        # Just verify both can be imported together
        assert __version_schema__ is not None
        assert MigrationRunner is not None

    def test_version_and_version_schema_both_exist(self):
        """Both __version__ and __version_schema__ are accessible."""
        from py_accountant import __version__, __version_schema__

        assert __version__ is not None
        assert __version_schema__ is not None
        assert isinstance(__version__, str)
        assert isinstance(__version_schema__, str)

