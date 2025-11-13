from importlib import import_module


def test_sdk_imports_available_from_root():
    pkg = import_module("py_accountant")
    assert hasattr(pkg, "sdk")
    # direct re-exports
    assert hasattr(pkg, "json")
    assert hasattr(pkg, "errors")
    assert hasattr(pkg, "use_cases")

    # import from py_accountant.sdk directly
    sdk_pkg = import_module("py_accountant.sdk")
    assert hasattr(sdk_pkg, "json")
    assert hasattr(sdk_pkg, "errors")
    assert hasattr(sdk_pkg, "use_cases")

