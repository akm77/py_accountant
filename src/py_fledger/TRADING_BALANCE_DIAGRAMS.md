# Trading Balance Diagrams

В этом файле представлены визуализации алгоритма `Book.trading_balance()`.

## PlantUML (основной поток)
```plantuml
@startuml
skinparam monochrome true
skinparam activityArrowColor Black
skinparam activityBorderColor Black
skinparam activityBackgroundColor White
skinparam defaultFontName monospace
start
:Вход options (startDate?, endDate?);
:Установить значения по умолчанию\nstart=Epoch, end=now(UTC);
:Инициализировать результат\nresult.currency={}, base=0;
:Выбрать все currencies;
repeat
  :Взять валюту C;
  partition DB {
    :credits_sum(C) = SUM(amount)\nJOIN Transaction->Account\nWHERE Account.currency=C \nAND credit=true \nAND createdAt BETWEEN [start,end];
    :debits_sum(C) = SUM(amount)\nJOIN Transaction->Account\nWHERE Account.currency=C \nAND credit=false \nAND createdAt BETWEEN [start,end];
  }
  :diff = debits_sum - credits_sum;
  :result.currency[C.code] = str(diff);
  if (C.id == 1?) then (да)
    :rate = 1.0;
  else (нет)
    :rate = C.exchange_rate; 
  endif
  :base = base + diff / rate;
repeat while (есть ещё валюты?) is (да)
:result.base = str(round(base));
:Вернуть { currency: map, base: str };
stop
@enduml
```

## Mermaid (эквивалентный поток)
```mermaid
flowchart TD
    A([Вход options: startDate?, endDate?]) --> B([Задать start = Epoch, end = now UTC])
    B --> C([Инициализировать result.currency = {}, base = 0])
    C --> D([Выбрать все currencies])
    D --> E{Есть ещё валюты?}
    E -->|Да| F([Взять валюту C])
    F --> G([credits_sum(C)])
    G --> H([debits_sum(C)])
    H --> I([diff = debits_sum - credits_sum])
    I --> J([result.currency[C.code] = to_string(diff)])
    J --> K{C.id == 1?}
    K -->|Да| L([rate = 1.0])
    K -->|Нет| M([rate = C.exchange_rate])
    L --> N([base = base + diff / rate])
    M --> N
    N --> E
    E -->|Нет| O([result.base = to_string(round(base))])
    O --> P([return { currency, base }])
```

## Примечания
- Mermaid-диаграмма использует синтаксис `flowchart TD` и избегает угловых скобок `< >` в подписях, чтобы не конфликтовать с парсером.
- Узлы упрощены, длинные подписи разбиты на запятые/пробелы, без Markdown-разметки.
- Отдельный файл с Mermaid-диаграммой: см. `TRADING_BALANCE.mmd`.
- PlantUML удобен для генерации PNG/SVG; при необходимости можно автоматизировать экспорт.
