def test_import_py_accountant():
    import py_accountant

    assert hasattr(py_accountant, "get_version")
    assert py_accountant.add(1, 2) == 3
