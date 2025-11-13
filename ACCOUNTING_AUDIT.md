# Бухгалтерский аудит и UX‑оценка пакета py_accountant (двойная запись)

Дата: 2025-11-13
Аудитор: системный архитектор и бухгалтер‑практик

Источники: rpg_py_accountant.yaml, README.md, docs/INTEGRATION_GUIDE.md, src/application/ports.py, src/application/use_cases_async/ledger.py, src/infrastructure/persistence/sqlalchemy/{uow,repositories_async}.py, src/presentation/cli/{ledger.py,infra.py}, examples/telegram_bot/*, pyproject.toml.

## 0) Резюме

- Назначение: ядро мультивалютного учёта с двойной записью, строгое разделение слоёв, async‑only runtime, Alembic — sync.
- Готовность к повседневной работе бухгалтера через CLI: 7/10. Постинг проводок и просмотр баланса реализованы, но формат ввода «SIDE:Account:Amount:Currency» требует аккуратности и знаний структуры плана счетов.
- Сильные стороны: доменная проверка баланса (LedgerValidator) с конвертацией в базовую валюту; чёткие async use case’ы; UoW на операцию; JSON‑сериализация детерминирована; примеры CLI и Telegram.
- Узкие места UX: отсутствие дружелюбных форм ввода (CSV/JSON/таблица), нет override даты операции, нет идемпотентности для защиты от дублей, нет явной «ошибочной матрицы» для маппинга в пользовательские сообщения, нет SDK‑фасада.
- Рекомендации (ROI↓):
  1) Ввести стабильный SDK‑слой и фасад «простого бухгалтера»: постинг, баланс, выписка, с нормализацией ошибок и JSON‑сериализацией.
  2) Улучшить UX CLI: альтернативы ввода проводок (CSV/JSON/--lines-file), поддержка пятого токена «Rate», флаг --occurred-at для ручной даты, человекочитаемые ошибки.
  3) Добавить идемпотентность постинга (idempotency_key в TransactionDTO/meta + уникальный индекс).
  4) Документация «шпаргалка бухгалтера»: шаблоны проводок, примеры для типовых операций, чек‑лист.

## 1) RPG‑сопоставление: узлы ↔ публичные точки

- Domain: `src/domain/ledger.py` (LedgerValidator, LedgerEntry) — балансировка после конверсии в базовую; `src/domain/currencies.py` — правила базы/курсов. ОК.
- Application: `src/application/use_cases_async/ledger.py` содержит:
  - AsyncPostTransaction(uow, clock)(lines, memo, meta) -> TransactionDTO — двойная запись с валидацией доменом, timestamp через clock.now().
  - AsyncGetAccountBalance(uow, clock)(account, as_of) -> Decimal — баланс счёта, fallback при NotImplemented в репозитории.
  - AsyncGetLedger(uow, clock)(account, window, meta, paging) -> list[RichTransactionDTO].
- Infrastructure: `AsyncSqlAlchemyUnitOfWork`, async репозитории CRUD‑уровня. TransactionRepository.add сохраняет journal + lines (включая exchange_rate на строке).
- Presentation (CLI): `src/presentation/cli/ledger.py` — команды `post`, `list`, `balance`; парсинг `--line` формата, сериализация JSON; код ошибок: 0/2/1.
- Публичный пакет: `py_accountant` пока не экспортирует фасадов — интеграторам нужны «глубокие» импорты.

Вывод: граф отражает слои корректно, но для внешнего потребителя (бот/веб/CLI‑расширения) отсутствует стабильный SDK‑фасад для «бухгалтерских» операций.

## 2) Модель двойной записи и контроль баланса

- Вход: список EntryLineDTO (сторона, счёт, сумма, валюта). Количество строк ≥ 2; суммы > 0. Валюты/счета должны существовать.
- Валидация: LedgerValidator конвертирует в базовую валюту и сравнивает дебет/кредит после money_quantize(2dp, HALF_EVEN); для небазовых валют требуется rate_to_base > 0; базовая валюта ровно одна.
- Результат: TransactionDTO с occurred_at = clock.now(), memo, meta. Репозиторий добавляет Journal и строки.
- Баланс счёта: через репозиторий (NotImplemented → ручной суммирующий fallback в use case).

С точки зрения бухгалтерии: правила консистентны и предсказуемы; критично иметь удобный ввод и понятные сообщения об ошибках.

## 3) UX для бухгалтера: текущее состояние

- Постинг через CLI: `ledger post --line "DEBIT:Assets:Cash:100:USD" --line "CREDIT:Income:Sales:100:USD"`.
  - Плюсы: быстро, не требует доп. файлов.
  - Минусы: формат легко испортить; нет поля даты (`occurred_at` всегда now()); нет встроенной поддержки курса на строке, хотя DTO его допускает.
- Выписка/баланс: `ledger list`, `ledger balance` — понятные флаги окна, пагинации, JSON.
- Telegram пример: есть парсер `/tx` с опциональным `:Rate`, что повышает пригодность для мультивалюты.

Градация ошибок (для UX):
- ValidationError — формат/валидация; DomainError — несбалансированность; ValueError — отсутствующие ресурсы. В CLI это всё маппится в exit 2 с выводом str(exc) — бухгалтеру не всегда очевидно, что исправлять.

## 4) Проблемы и зазоры (по RPG и UX)

- Публичный фасад отсутствует: нет `py_accountant.sdk` с ясными функциями «провести проводку», «дать баланс», «дать выписку» + нормализация ошибок.
- Формат ввода ограничен «SIDE:...»: нет `--lines-file` (CSV/JSON), нет множественных проводок в файле за один запуск, нет `--occurred-at`.
- Нет идемпотентности: повторный запуск может создать дубль.
- Сообщения об ошибках не стандартизованы для «пользовательской» поверхности: нет кода/категории/подсказки.
- Документация ориентирована на инженера; бухгалтерские примеры присутствуют, но без «шпаргалок» операций.

## 5) Рекомендации по улучшению UX (конкретные и измеримые)

1) SDK‑слой для бухгалтерских сценариев (публичный импорт)
   - Создать пакет `src/py_accountant/sdk/` и экспортировать из `src/py_accountant/__init__.py` стабильные символы:
     - `from .sdk import post_transaction, get_account_balance, get_ledger, build_uow, to_json, map_error`
   - Реализация:
     - `sdk/uow.py`: `build_uow(url|env) -> AsyncUnitOfWork` с dual‑URL нормализацией.
     - `sdk/use_cases.py`: тонкие фасады над AsyncPostTransaction/AsyncGetAccountBalance/AsyncGetLedger.
     - `sdk/json.py`: сериализация Decimal/datetime.
     - `sdk/errors.py`: `UserInputError`, `DomainViolation`, `MissingResource`, `UnexpectedError`; маппинг из ValidationError/DomainError/ValueError.
   - Критерий приёмки: интегратор может провести проводку и получить баланс, импортируя только из `py_accountant.sdk`.

2) Улучшения CLI «ledger post» (без ломки совместимости)
   - Добавить `--occurred-at <ISO>` для установки даты транзакции; при наличии — прокидывать в use case через Clock‑stub.
   - Расширить формат `--line` до 5‑го токена: `SIDE:Account:Amount:Currency[:Rate]` (как в Telegram parser). При наличии Rate писать в DTO.exchange_rate.
   - Добавить `--lines-file <path>`:
     - CSV: колонки side, account, amount, currency, rate (опц.).
     - JSON: массив объектов с этими полями.
   - Человекочитаемые ошибки: перехватывать ValidationError/DomainError/ValueError и печатать подсказку (например, «Проверьте, что базовая валюта установлена и заданы курсы небазовых валют»).
   - Критерий приёмки: бухгалтер может провести мультивалютную проводку с заданной датой и курсом без ручной сборки строки.

3) Идемпотентность постинга
   - Добавить необязательный `--idempotency-key <str>` → сохранять в TransactionDTO.meta["idempotency_key"].
   - На уровне ORM в JournalORM: уникальный индекс на (idempotency_key) с условием non‑null; репозиторий перед вставкой проверяет существование ключа и возвращает существующую транзакцию.
   - Критерий приёмки: повторный вызов с тем же ключом не создаёт дублей.

4) «Матрица ошибок бухгалтера» и подсказки
   - В `sdk/errors.py` описать коды и рекомендации (например, `missing_base_currency`, `unknown_currency`, `unbalanced_ledger`, `invalid_line_format`).
   - CLI и Telegram‑обработчики используют маппинг для дружелюбных сообщений.

5) Документация для бухгалтера
   - Новый раздел в README: «Шпаргалка проводок» (примеры: продажа, покупка, конвертация, списание комиссии, переоценка курсов).
   - Расширить docs/INTEGRATION_GUIDE.md: примеры JSON/CSV загрузки.

6) Мелкие улучшения удобства
   - Команда `account list --tree` для показа плана счетов с отступами.
   - В `ledger list` — флаг `--human` с красивой табличной печатью.

## 6) Проектные ограничения и совместимость

- Python 3.13+: с точки зрения бухгалтерского UX не критично, но сужает аудиторию. При возможности — расширить до 3.11+ (проверить типизацию/PEP‑фичи).
- Dual‑URL: сохранить текущее правило (Alembic — sync; runtime — async) и добавить раннюю проверку в SDK.

## 7) Мини‑контракты (что обещает поверхность)

- post_transaction(uow, lines, memo?, meta?, occurred_at?) -> TransactionDTO
  - Вход: list[EntryLineDTO|dict] c нормализацией, опц. occurred_at.
  - Ошибки: UserInputError | DomainViolation | MissingResource.
- get_account_balance(uow, account, as_of?) -> Decimal
- get_ledger(uow, account, window?, paging?) -> list[RichTransactionDTO]

Краевые случаи: пустые строки, отрицательные суммы, неизвестные валюты/счета, отсутствие базовой валюты/курсов, большие объёмы (paging), часовые пояса (на входе ISO→UTC).

## 8) Дорожная карта (2 итерации по 2–3 дня)

Итерация 1 (SDK и CLI расширение):
- Добавить пакет `py_accountant/sdk` с фасадами и маппингом ошибок; экспорт из корня пакета.
- CLI: `--occurred-at`, поддержка 5‑го токена Rate, дружелюбные сообщения.
- Тесты:
  - unit: ошибка формата строки, отсутствие базы, несбалансированность.
  - integration (CLI): постинг с Rate и occurred_at; баланс.

Итерация 2 (файловые форматы и идемпотентность):
- CLI: `--lines-file` (CSV/JSON).
- Идемпотентность (мета + индекс), репозиторный guard.
- Документация: шпаргалка и примеры.

## 9) Оценка удобства для бухгалтера (после внедрения)

- Создание проводок: из 5 действий до 2–3 (готовый шаблон + файл/копипаст JSON/CSV). Ошибки с подсказками → меньше возвратов.
- Баланс по счёту: однозначный флаг `--as-of`, чтение суммы в человекочитаемом виде или JSON.
- Мультивалюта: явная поддержка курса на строке, требование базовой валюты — с понятной инструкцией.

## 10) Чек‑лист качества

- Архитектура слоёв (RPG) сохранена: домен чистый, use case’ы тонкие, репозитории CRUD.
- Публичная поверхность для «бухгалтерских» задач: добавлена (SDK/CLI улучшения).
- Сообщения об ошибках стандартизованы.
- Идемпотентность постинга реализована (или спланирована под индекс).

## Приложение A. Быстрые примеры

- Проводка (JSON‑файл lines.json):
```json
[
  {"side":"DEBIT","account":"Assets:Cash","amount":"100","currency":"USD"},
  {"side":"CREDIT","account":"Income:Sales","amount":"100","currency":"USD"}
]
```
Запуск: `python -m presentation.cli.main ledger post --lines-file lines.json --memo "Sale" --occurred-at 2025-11-13T10:00:00Z --json`

- Проводка с курсом строки (пятая часть):
`ledger post --line "DEBIT:Assets:Broker:100:EUR:1.120000" --line "CREDIT:Assets:Cash:112:USD"`

## Приложение B. Матрица ошибок (черновик кодов)

- invalid_line_format → «Формат строки: SIDE:Account:Amount:Currency[:Rate]»
- non_positive_amount → «Сумма должна быть > 0»
- missing_base_currency → «Установите базовую валюту: currency set-base USD»
- unknown_currency/unknown_account → «Создайте ресурс перед постингом»
- unbalanced_ledger → «Дебет/Кредит не сходятся в базе; проверьте курсы и суммы»

---

Документ использует методику RPG: узлы → слои/модули; рёбра → зависимости. Сопоставление графа и фактического API показало соответствие слоёв и отсутствие стабильного фасада для бухгалтерских сценариев; предложенные изменения устраняют зазор без усложнения домена.

