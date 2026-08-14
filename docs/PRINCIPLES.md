# Project Principles

## Purpose

Документація фіксує стабільні правила для відтворюваного наукового benchmark,
який запускає CDLG і передає валідовані артефакти до `bpm_prediction`.

## Authority

Для першого експерименту схвалена design specification є Canon і має перевагу
над припущеннями агента, кодом та історичними матеріалами. `AGENTS.md` визначає
операційні та repository-boundary правила.

## Principles

### Principle: Complete pipeline acceptance

Запуск є успішним лише після завершення та перевірки всього pipeline. Частковий
або неповністю валідований output не є valid dataset.

Rationale: це прямо підтверджено вимогою про неприйнятність неповного pipeline і
підкріплено strict validation contract у specification.

Implications: acceptance має перевіряти XES, BPMN/PTML, generation statistics,
mapping rules, provenance та checksums; failure не може маскуватися як success.

### Principle: Reproducible evidence

Кожен прийнятий dataset повинен мати пов’язаний evidence bundle з конфігурацією,
версією CDLG, командою запуску, raw output, reports, metadata і checksums.

Rationale: це вимога схваленої specification для research-ready результату.

Implications: результати без достатньої provenance не можна використовувати як
підтверджений експериментальний evidence.

### Principle: Explicit external boundary

CDLG запускається як зовнішній pinned runtime. Benchmark не імпортує, не копіює,
не vendor-ить і не змінює його source.

Rationale: це зафіксована repository та licensing boundary у `AGENTS.md` і
specification.

Implications: обмін відбувається через process arguments, files, exit status,
stdout і stderr.

### Principle: Separate approval for CDLG changes

CDLG є зовнішнім проєктом під окремою ліцензією. Будь-яка пропозиція змінити
CDLG або його pinned checkout повинна бути винесена на окреме обговорення,
explicitly approved і прийнята разом із зафіксованими ризиками.

Rationale: benchmark не володіє upstream CDLG і не може одноосібно змінювати його
код або непомітно змінювати експериментальну основу.

Implications: якщо потрібна поведінка неможлива через зовнішній process boundary,
роботу потрібно зупинити, описати альтернативи, наслідки для ліцензії,
відтворюваності та методології, а також отримати окреме рішення до будь-якої
правки CDLG.

### Principle: Contract before implementation

Реалізація повинна відповідати схваленій specification. Суперечність між
specification, observed CDLG behavior і кодом потребує explicit reconciliation,
а не мовчазного вибору одного джерела.

Rationale: specification визначена Canon для першого експерименту.

Implications: methodology, artifact contract і repository boundary не можна
змінювати як incidental implementation detail.

### Principle: Observable acceptance

Приймання визначається перевірюваними результатами та artifact contract, а не
лише наявністю коду, unit tests або збільшенням coverage.

Rationale: specification вимагає layered tests і strict local validation.

Implications: meaningful implementation slices повинні мати acceptance criteria,
focused validation і, де потрібно, end-to-end smoke test.

## Decision Rules

- Якщо джерела суперечать одне одному, спочатку застосовувати authority order,
  потім фіксувати conflict або reconciliation decision.
- Не перетворювати implementation detail на Canon без підтвердження.
- Не публікувати partial output як completed dataset.
- Не розширювати перший сценарій drift без окремого design decision.

## Open Questions

Наразі відкритих питань для Canon першого експерименту не зафіксовано.

## Related Documents

- [`AGENTS.md`](../AGENTS.md)
- [`README.md`](../README.md)
- [`CDLG Versioned XES Wrapper Design`](wrapper-design.md)
