# Исследовательская записка: измерение agency в contextual quote

**Дата:** 2026-09-04  
**Аудитория:** продуктовая, data/ML и пилотная команда.  
**Scope:** как измерять, помогает ли contextual quote клиенту самостоятельно
понять и совершить нужное действие в трансграничном переводе; не является
юридическим, комплаенс- или инвестиционным заключением.

## Прямой вывод

Для проекта нельзя принять CTR, частоту переводов или краткосрочный финансовый
well-being за меру agency. Нужна композиция из (1) понимания и отсутствия
давления, (2) беспрепятственного выполнения обычного перевода, (3) причинного
изменения outcome против holdout и (4) жёстких execution/safety guardrails.

## Claim-to-source ledger

| Claim | Источник | Дата / доступ |
| --- | --- | --- |
| Financial well-being включает воспринимаемые security и freedom of choice; CFPB предлагает валидированную шкалу, но она измеряет более широкий и долгосрочный конструкт. | [CFPB Financial Well-Being Scale](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/) | Страница обновлена 2023-08-08; прочитано 2026-09-04. |
| Financial skill/self-efficacy можно измерять вопросами о сложных финансовых решениях, выполнении намерений, достаточности информации и потребности в advice. | [CFPB Measuring Financial Skill](https://files.consumerfinance.gov/f/documents/bcfp_financial-well-being_measuring-financial-skill_guide.pdf) | PDF CFPB, 2018; прочитано 2026-09-04. |
| Для decision support измеряют uncertainty, informedness, clarity of values и perceived support; перенос в перевод — аналитическая адаптация, не валидированная финтех-шкала. | [AHRQ: Shared Decision-Making Measures](https://www.ahrq.gov/sdm/measures-data-funding/index.html) | Прочитано 2026-09-04. |
| Usability измеряется в контексте заданных пользователей/целей как effectiveness, efficiency, satisfaction. | [ISO 9241-110](https://www.iso.org/obp/ui?_escaped_fragment_=iso:std:iso:9241:-110:dis:ed-2:v1:en) | Проект стандарта с ссылкой на ISO 9241-11; прочитано 2026-09-04. |
| Randomized experiment устанавливает причинный эффект фичи на поведение; OEC должен отличаться от диагностических краткосрочных метрик и учитывать долгосрочные ловушки. | [Kohavi et al., Online Experimentation at Microsoft](https://www.microsoft.com/en-us/research/publication/online-experimentation-at-microsoft/); [Pitfalls of Long-Term Online Controlled Experiments](https://www.microsoft.com/en-us/research/publication/pitfalls-of-long-term-online-controlled-experiments/) | 2009 / 2016; прочитано 2026-09-04. |

## Ограничения

Медицинские шкалы decision support полезны как структура конструкта, но не дают
готовой валидной шкалы для банковского перевода. CFPB-шкалы шире одной операции
и не подходят как primary metric короткого эксперимента. Поэтому предлагаемый
`Agency pulse` — новый, пилотный инструмент: его нельзя называть валидированной
шкалой и применять для профилирования клиентов.
