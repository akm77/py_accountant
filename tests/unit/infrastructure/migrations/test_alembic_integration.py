"""Unit tests for Alembic integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from py_accountant.infrastructure.migrations.alembic_integration import include_in_alembic


def test_include_in_alembic_adds_version_locations():
    """include_in_alembic() adds py_accountant migrations to version_locations."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = []
    mock_context.script = mock_script

    # Act
    include_in_alembic(mock_context)

    # Assert
    assert mock_script.version_locations is not None
    assert len(mock_script.version_locations) == 2
    # First should be py_accountant versions
    assert "versions" in mock_script.version_locations[0]
    # Second should be original location
    assert mock_script.version_locations[1] == "/project/alembic"


def test_include_in_alembic_with_table_prefix():
    """include_in_alembic() accepts table_prefix parameter."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = []
    mock_context.script = mock_script

    # Act - Should not raise
    include_in_alembic(mock_context, table_prefix="pyacc_")

    # Assert - Verify it still added locations
    assert mock_script.version_locations is not None
    assert len(mock_script.version_locations) == 2


def test_include_in_alembic_with_schema():
    """include_in_alembic() accepts schema parameter."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = []
    mock_context.script = mock_script

    # Act - Should not raise
    include_in_alembic(mock_context, schema="py_accountant")

    # Assert - Verify it still added locations
    assert mock_script.version_locations is not None
    assert len(mock_script.version_locations) == 2


def test_include_in_alembic_without_script():
    """include_in_alembic() handles context without script gracefully."""
    # Arrange
    mock_context = MagicMock()
    mock_context.script = None

    # Act - Should not raise, just log warning
    include_in_alembic(mock_context)  # No exception expected


def test_include_in_alembic_versions_path_exists():
    """include_in_alembic() uses existing versions directory."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = []
    mock_context.script = mock_script

    # Act
    include_in_alembic(mock_context)

    # Assert - Verify path points to real versions directory
    versions_path = Path(mock_script.version_locations[0])
    assert versions_path.name == "versions"
    # Should be relative to migrations module
    assert "infrastructure/migrations/versions" in str(versions_path) or "migrations/versions" in str(versions_path)


def test_include_in_alembic_logs_operation():
    """include_in_alembic() logs the operation."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = []
    mock_context.script = mock_script

    # Act
    with patch("py_accountant.infrastructure.migrations.alembic_integration.logger") as mock_logger:
        include_in_alembic(mock_context, table_prefix="test_", schema="public")

        # Assert - Should log info message
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "py_accountant migrations" in log_message


def test_include_in_alembic_preserves_existing_locations():
    """include_in_alembic() preserves existing version_locations."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = ["/other/versions"]
    mock_context.script = mock_script

    # Act
    include_in_alembic(mock_context)

    # Assert - Should have py_accountant first, then original, then project dir
    assert len(mock_script.version_locations) >= 2
    assert "versions" in mock_script.version_locations[0]
    assert "/other/versions" in mock_script.version_locations


def test_include_in_alembic_handles_tuple_locations():
    """include_in_alembic() converts tuple version_locations to list."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = ("/existing/versions",)  # Tuple
    mock_context.script = mock_script

    # Act
    include_in_alembic(mock_context)

    # Assert - Should be converted to list and modified
    assert isinstance(mock_script.version_locations, list)
    assert len(mock_script.version_locations) >= 2


def test_include_in_alembic_handles_none_locations():
    """include_in_alembic() initializes None version_locations."""
    # Arrange
    mock_context = MagicMock()
    mock_script = MagicMock()
    mock_script.dir = "/project/alembic"
    mock_script.version_locations = None
    mock_context.script = mock_script

    # Act
    include_in_alembic(mock_context)

    # Assert - Should initialize and populate
    assert mock_script.version_locations is not None
    assert isinstance(mock_script.version_locations, list)
    assert len(mock_script.version_locations) >= 2


def test_include_in_alembic_context_without_script_attribute():
    """include_in_alembic() handles context without script attribute."""
    # Arrange
    mock_context = MagicMock(spec=[])  # No attributes

    # Act - Should not raise
    with patch("py_accountant.infrastructure.migrations.alembic_integration.logger") as mock_logger:
        include_in_alembic(mock_context)

        # Assert - Should log warning
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "no script directory" in warning_message

