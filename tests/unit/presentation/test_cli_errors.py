"""Тесты ошибок и граничных сценариев CLI.

Цели:
- Проверить единообразный код выхода 2 для DomainError (валидационные ошибки).
- Проверить код выхода 1 для неожиданных исключений.
- Набор охватывает основные команды и парсинг аргументов/линий.

Принципы:
- Каждый тест изолирован: in‑memory UoW разделяется по PYTEST_CURRENT_TEST.
- Не проверяем текст сообщения (только код выхода), чтобы не делать тесты хрупкими.
- Добавлены edge‑кейсы: неизвестная политика, fx:batch с некорректным JSON/курсами, отрицательная сумма, неверный формат meta.
"""
from __future__ import annotations

import importlib
from pathlib import Path

from presentation.cli.main import main

# --- Базовые ошибки ---

def test_currency_set_base_unknown():
    # Попытка назначить базовую валюту до её создания -> DomainError
    rc = main(["currency:set-base", "ZZZ"])
    assert rc == 2


def test_fx_update_invalid_rate():
    # Валюта создаётся, но курс недопустим (<=0)
    assert main(["currency:add", "GBP"]) == 0
    rc = main(["fx:update", "GBP", "0"])  # invalid rate
    assert rc == 2


def test_account_add_unknown_currency():
    # Создаём счёт в несуществующей валюте
    rc = main(["account:add", "Assets:Cash", "XXX"])  # currency XXX not created
    assert rc == 2


def test_tx_post_missing_account():
    # Валюта есть, счета нет -> ошибка при постинге
    assert main(["currency:add", "USD"]) == 0
    rc = main(["tx:post", "--line", "DEBIT:Assets:Cash:10:USD", "--line", "CREDIT:Income:Sales:10:USD"])
    assert rc == 2


def test_tx_post_invalid_line_format():
    # Линия без требуемых сегментов
    rc = main(["tx:post", "--line", "BADFORMAT"])
    assert rc == 2


def test_ledger_list_invalid_account_name():
    # Формат счёта должен содержать двоеточие
    rc = main(["ledger:list", "InvalidNameWithoutColon"])
    assert rc == 2


def test_unknown_policy_flag():
    # Глобальный флаг политики с неизвестным значением
    rc = main(["--policy", "some_weird_mode", "currency:list"])  # parser: global флаги до команды
    assert rc == 2


# --- fx:batch сценарии ---

def test_fx_batch_file_not_found(tmp_path: Path):
    p = tmp_path / "missing.json"
    rc = main(["fx:batch", str(p)])
    assert rc == 2


def test_fx_batch_invalid_json_structure(tmp_path: Path):
    # Валюта нужна для проверки существования, но JSON не список -> ошибка
    assert main(["currency:add", "USD"]) == 0
    f = tmp_path / "bad.json"
    f.write_text("{}", encoding="utf-8")  # объект вместо списка
    rc = main(["fx:batch", str(f)])
    assert rc == 2


def test_fx_batch_invalid_rate(tmp_path: Path):
    # Обновление с нулевым курсом в списке
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:add", "EUR"]) == 0
    f = tmp_path / "bad_rates.json"
    f.write_text('[{"code": "EUR", "rate": 0}]', encoding="utf-8")
    rc = main(["fx:batch", str(f)])
    assert rc == 2


# --- Отрицательные и некорректные суммы ---

def test_tx_post_negative_amount():
    assert main(["currency:add", "USD"]) == 0
    assert main(["account:add", "Assets:Cash", "USD"]) == 0
    assert main(["account:add", "Income:Sales", "USD"]) == 0
    rc = main(["tx:post", "--line", "DEBIT:Assets:Cash:-5:USD", "--line", "CREDIT:Income:Sales:-5:USD"])
    assert rc == 2


# --- Некорректные meta фильтры ---

def test_ledger_list_invalid_meta_item():
    # meta элемент без '=' -> ошибка парсинга
    rc = main(["ledger:list", "Assets:Cash", "--meta", "justkey"])
    assert rc == 2


# --- Неожиданная ошибка ---

def test_unexpected_error(monkeypatch):
    # Подменяем _get_uow так, чтобы выбросить RuntimeError -> код 1
    cli_mod = importlib.import_module("presentation.cli.main")
    assert hasattr(cli_mod, "_get_uow")

    def boom(_):  # noqa: D401
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_mod, "_get_uow", boom)
    rc = main(["currency:list"])  # любая команда
    assert rc == 1


# --- Дополнительные негативные сценарии ---

def test_balance_get_unknown_account():
    # Валюта есть, счёт отсутствует — баланс агрегируется через transaction repo (возвращает 0),
    # но мы хотим убедиться что отсутствие транзакций НЕ является ошибкой: команда должна вернуть 0.
    # Это не DomainError, а контроль корректности поведения.
    assert main(["currency:add", "USD"]) == 0
    rc = main(["balance:get", "Assets:Cash"])  # счёт не создан, баланс = 0 по логике репо
    assert rc == 0


def test_trading_detailed_missing_base():
    # Отсутствует обязательный --base
    rc = main(["trading:detailed", "--base", ""])  # пустая строка => DomainError в use case
    assert rc == 2
