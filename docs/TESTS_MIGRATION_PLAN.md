# План миграции и утилизации старых тестов

Дата: 2025-11-11
Источник: REFACTORING_RPG_PLAN.md / REFACTORING_RPG_ITERATIONS.yaml
Цель: Сохранить максимально полезное покрытие, избежать массового красного состояния CI и устранить тесты, которые тормозят рефакторинг или не несут ценности.

## 1. Почему не удаляем всё
Полное удаление:
- Потеря регрессионного сигнала (особенно по FX TTL, логированию, CLI потокам).
- Риск незамеченных регрессий при переносе логики из репозиториев в доменные сервисы.
- Усложнит верификацию достижений метрик (некорректное сравнение до/после).

Подход: итеративная конверсия + выборочное удаление низкоценностных тестов.

## 2. Категории тестов
| Категория | Критерии | Действие |
|-----------|----------|----------|
| KEEP-ASIS | Не затрагивают переносимые слои (напр. структурные проверки docs, базовый импорт пакета) | Оставить до финала, затем пересмотреть (I29) |
| ADAPT-SHALLOW | Ссылаются на DTO/Protocols, меняющихся по именам/полям, но сценарий тот же | Минимальная правка импорта/имён (Ит. после I09/I11) |
| REWRITE-DOMAIN | Проверяют бизнес-логику, которая будет вынесена из инфраструктуры | Ранний перенос в domain/* новые тесты; старые помечаем xfail до удаления |
| MERGE/COALESCE | Несколько тестов проверяют одно и то же комбинациями параметров | Объединить в параметризованный тест после стабилизации интерфейса |
| DROP-TRIVIAL | Тривиальные проверки import sqlalchemy, тестирующие stdlib или демо функции | Удалить в I29 (migration_cleanup) |
| UPGRADE-CLI | Тесты старого sync CLI, которые станут async Typer | Переписать на invoke + asyncio, старые — xfail либо временно skip |
| PERF-OPTIONAL | Производительные / нагрузочные (долгие) тесты | Вынести в отдельный marker slow/perf; не блокируют мердж |
| OBSOLETE | Тестирует удаляемый слой (async_bridge, sync repositories) | Удалить в итерациях I27–I28 |

## 3. Инвентаризация (предварительная)
| Файл | Категория | Причина / Нужное действие |
|------|-----------|---------------------------|
| tests/unit/test_smoke.py | DROP-TRIVIAL | Проверяет импорт sqlalchemy — лишнее после baseline метрик |
| tests/unit/test_package_import.py | KEEP-ASIS (позже возможно DROP) | Минимальный публичный импорт; оставить до финального релиза |
| tests/unit/test_fx_ttl.py | REWRITE-DOMAIN | TTL логика перейдёт в FxAuditTTLService; создать domain версию раннее (I08) |
| tests/unit/test_logging.py | KEEP-ASIS | Конфигурация логирования инфраструктуры не меняется кардинально |
| tests/unit/test_parity_internal_consistency.py | UPGRADE-CLI | Зависит от старого CLI main; переписать на новое Typer API (I24–I25) |
| tests/integration/test_async_fx_ttl.py | ADAPT-SHALLOW | Перенастроить на новый UoW, интерфйс TTL сервис вызывает репозиторий через use case |
| tests/perf/test_cli_perf.py | PERF-OPTIONAL + UPGRADE-CLI | Перенести на async CLI поздно (после I26), пометить marker 'slow' |
| tests/unit/application/test_async_use_cases_smoke.py | SPLIT (REWRITE-DOMAIN + ADAPT-SHALLOW) | Разбить: часть логики станет domain; остальное адаптировать после use case рефакторинга (I15–I19) |
| tests/unit/application/test_async_repositories.py | ADAPT-SHALLOW | Методы CRUD сохраняются; убрать проверку бизнес-агрегаций |
| tests/unit/application/test_trading_balance_detailed.py | REWRITE-DOMAIN | Должен стать domain/trading_balance_converted тестом (I07) |
| tests/unit/application/test_quantize_edges.py | KEEP-ASIS → MOVE | Переместить/адаптировать к domain/quantize (I02) |
| tests/unit/application/test_ports_and_dtos.py | ADAPT-SHALLOW | После I09/I11 обновить DTO поля и убрать лишние Protocol ссылки |
| tests/unit/application/test_async_ports_protocols.py | ADAPT-SHALLOW | Проверить только async Protocols после I11 |

(Полная таблица дополняется при начале I29; сохранить как артефакт `tests/report/test_inventory.md`).

## 4. Пошагова�� стратегия миграции
1. Ранние доменные итерации (I01–I08): создавать новые domain-тесты ПАРАЛЛЕЛЬНО, не удаляя старые.
2. После успешного прогона новых domain тестов — маркировать старые дубли xfail (pytest.mark.xfail(reason="migrated to domain")) чтобы не ламать CI, но сигнализировать о долге.
3. На этапе DTO рефакторинга (I09): временно держать два набора DTO тестов (новый + адаптированный), затем удалить legacy assertions после freeze (I11).
4. После унификации портов (I11): выполнить массовый grep по старым sync Protocol классам; для найденных тестов — адаптация или xfail.
5. При внедрении нового UoW (I14): интеграционные тесты обновляются; старые проверки retry удаляются (DROP-TRIVIAL / OBSOLETE).
6. CLI (I21–I26): перенести вызовы через Typer runner (`CliRunner`/`typer.testing`) — старые main([...]) тесты → UPGRADE-CLI; когда все перенесены — удалить старые.
7. Cleanup (I29):
   - Удалить все xfail помеченные более чем 3 итерации назад.
   - Удалить DROP-TRIVIAL.
   - Свести дубли (MERGE/COALESCE) параметризацией.
8. Метрики (I30/I31): считать покрытие только по актуальным тестам (exclude removed patterns).

## 5. Критерии удаления
Удаляем тест без миграции, если ВСЕ:
- Не покрывает уникальную ветку кода после рефакторинга.
- Логика будет удалена полностью (модуль исчезает).
- Не несёт контрактного смысла (пример: импорт внешней библиотеки).
- Не требуется для регресса безопасности/устойчивости.

## 6. Автоматизация
Добавить вспомогательный скрипт (позже, опционально):
- Сканирует тесты и классифицирует по эвристикам (regex на имя файла, содержимое import).
- Генерирует `tests/report/test_inventory.json`.

## 7. Политика xfail/skip
| Маркер | Использование | Срок снятия |
|--------|---------------|------------|
| xfail(migrated to domain) | Старый тест заменён новым domain аналогом | До I29 |
| skip(obsolete) | Тест на удаляемый модуль, мешает прогону | Удалить к I27/I28 |
| slow | Производительный тест (perf) | Никогда не блокирует merge |

## 8. Обновление YAML плана
Итерация I29 уже содержит `tests.migration_cleanup`. Дополнение: перед I09 вставить микрошаг **I08A test_inventory_snapshot**.

Предложение для вставки (дифф):
```
- id: I08A
  name: tests.inventory_snapshot
  scope:
    - generate initial inventory report tests/report/test_inventory.md
    - mark candidates for xfail
  dependencies: [I08]
  deliverables:
    - tests/report/test_inventory.md
  tests: []
  acceptance_criteria:
    - Inventory file exists and lists categories
  risk_mitigation: "Не меняет код, только аналитика"
```

## 9. Контроль качества миграции тестов
Метрики:
- % тестов, переведённых на новую архитектуру (цель ≥80% до I27).
- Кол-во xfail ≤ 10 к моменту I29.
- Дубликаты (одинаковые asserts разных файлов) → 0 к I35.

## 10. Резюме действий «Удалить vs Переписать»
Удалить:
- test_smoke_sqlalchemy_import
- Любые тесты на прямой ImportError sync repositories после удаления
- Тривиальные демонстрационные тесты, не связанные с критичным функционалом

Переписать/Перенести:
- TTL, trading balance, ledger балансировка, parity/report — так как отражают бизнес правила.
- CLI тесты — на новый async CLI.
- DTO/Ports — после стабилизации интерфейсов.

Оставить без изменений (до финала):
- Логирование (проверяет формат/JSON структуры)
- Документационные тесты (проверка обязательных секций)

---
Конец документа.

