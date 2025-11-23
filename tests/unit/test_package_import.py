def test_import_core_modules() -> None:
    # Базовая проверка, что core-модули доступны для импорта
    import application  # noqa: F401
    import domain  # noqa: F401
    import infrastructure  # noqa: F401

    # Дополнительно проверим, что async use cases и ports доступны
    from application import ports  # noqa: F401
    from application.use_cases_async import ledger  # noqa: F401

    assert hasattr(ports, "AsyncUnitOfWork")
    assert hasattr(ledger, "AsyncPostTransaction")
