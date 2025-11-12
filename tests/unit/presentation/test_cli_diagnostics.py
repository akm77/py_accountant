from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(reason="migrated to async CLI foundation; currency diagnostics replaced by I22 commands", strict=False)

# Legacy diagnostics:rates tests removed (I22) in favor of currency list commands.
# New currency CLI tests live under tests/integration/cli/test_cli_currencies.py.
