# Test Inventory Snapshot (I08A)

Generated: 2025-11-11
Scope: Categorize existing tests for migration according to RPG refactor plan.

Legend (categories):
- KEEP-ASIS: keep unchanged for now
- ADAPT-SHALLOW: minor updates (imports, names) after DTO/Ports refactor
- REWRITE-DOMAIN: rewrite as domain tests; old tests to be xfail then removed in I29
- UPGRADE-CLI: rewrite for new async Typer CLI; old tests xfail/skip until CLI ready
- DROP-TRIVIAL: remove at I29, low value
- OBSOLETE: remove when module is removed (I27–I28)
- PERF-OPTIONAL: slow tests, non-blocking
- SPLIT: partially rewrite to domain and partially adapt
- MOVE: move tests to domain package without logic changes

## KEEP-ASIS
- tests/docs/test_docs_sections_present.py
- tests/docs/test_parity_expected_format.py
- tests/docs/test_no_legacy_string.py
- tests/docs/test_examples_exist.py
- tests/unit/test_logging.py
- tests/unit/domain/test_value_objects.py
- tests/unit/domain/test_currency_code_validation.py
- tests/unit/domain/test_account_balance_service.py
- tests/unit/domain/test_exchange_rate_policy.py
- tests/integration/config/test_dual_url_consistency.py
- tests/integration/alembic/test_sync_migrations_still_work.py
- tests/integration/ledger/test_alembic_migration.py
- tests/integration/ledger/test_performance_indices.py
- tests/integration/ledger/test_migration_is_base_column.py
- tests/unit/test_settings.py
- tests/unit/infrastructure/test_async_engine.py

## ADAPT-SHALLOW
- tests/conftest.py (fixture Async UoW wiring)
- tests/integration/test_async_fx_ttl.py
- tests/integration/repositories/test_sqlalchemy_repos.py
- tests/unit/application/test_async_repositories.py
- tests/unit/application/test_ports_and_dtos.py
- tests/unit/application/test_async_ports_protocols.py
- tests/unit/application/test_use_cases.py
- tests/unit/use_cases/test_use_cases_smoke.py
- tests/integration/ledger/test_exchange_rates_flow.py
- tests/integration/ledger/test_trading_balance_detailed_flow.py
- tests/integration/ledger/test_ledger_pagination.py
- tests/integration/ledger/test_balance_cache_flow.py (pending cache strategy)
- tests/unit/infrastructure/test_async_uow.py
- tests/unit/application/test_list_ledger_validation.py

## REWRITE-DOMAIN
- tests/unit/test_fx_ttl.py
- tests/unit/application/test_trading_balance_detailed.py
- tests/unit/application/test_recalculate_balance.py
- tests/unit/application/test_update_exchange_rates_negative.py
- tests/unit/application/test_exchange_rate_policy_weighted_average_edge.py
- tests/unit/application/test_quantize_edges.py (MOVE to domain + minor edits)
- tests/unit/application/test_list_ledger_validation.py (if contains domain rules)
- tests/unit/test_fx_audit.py (align with TTL service API)

## UPGRADE-CLI
- tests/perf/test_cli_perf.py (also PERF-OPTIONAL)
- tests/unit/presentation/test_cli_trading_detailed_normalize.py
- tests/unit/presentation/test_cli_diagnostics_parity.py
- tests/unit/presentation/test_cli_basic.py
- tests/unit/presentation/test_cli_fx_batch_override.py
- tests/unit/presentation/test_cli_diagnostics.py
- tests/unit/presentation/test_cli_unbalanced_tx.py
- tests/unit/presentation/test_cli_errors.py
- tests/unit/presentation/test_cli_diagnostics_human_empty.py
- tests/e2e/cli/test_cli_flow.py
- tests/unit/test_parity_internal_consistency.py
- tests/integration/ledger/test_fx_ttl_cli.py
- tests/examples/test_tx_parser.py

## DROP-TRIVIAL
- tests/unit/test_smoke.py

## OBSOLETE
- tests/unit/presentation/test_run_sync.py (sync bridge planned for removal)
- tests/unit/infrastructure/test_async_uow_retries.py (retry logic removed in I14)
- tests/unit/infrastructure/test_async_uow_statement_timeout.py (timeout injection removed in I14)
- tests/unit/application/test_inmemory_adapters.py (if in-memory adapters removed)

## PERF-OPTIONAL
- tests/perf/test_cli_perf.py

## SPLIT
- tests/unit/application/test_async_use_cases_smoke.py (split across domain tests + shallow use case smoke)

## MOVE
- tests/unit/application/test_quantize_edges.py (to domain/quantize)

---
Notes:
- This inventory is a planning artifact; no tests were modified.
- For UPGRADE-CLI/REWRITE-DOMAIN categories, add pytest.mark.xfail(reason="migrated to async CLI / domain") when the new equivalents are added; remove in I29.
- "tests/integration/ledger/test_balance_cache_flow.py" depends on the decision about balance cache; currently marked ADAPT-SHALLOW; re-evaluate after cache strategy is finalized.

