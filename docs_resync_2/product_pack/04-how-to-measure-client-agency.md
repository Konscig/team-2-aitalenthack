# Как измерять «возможность клиента принять решение»

## Короткий ответ

Не измеряйте это одной метрикой. Для contextual quote успех — не «клиент чаще
кликнул» и не «перевёл больше». Он должен:

1. понять, что ему показали **факт и актуальный quote**, а не прогноз или
   обещание;
2. сохранить контроль над решением и возможность сразу совершить срочный
   перевод;
3. при этом дать доказуемый инкрементальный эффект относительно ситуации, где
   тот же eligible client видит обычный путь без hook;
4. не ухудшить исполнимые условия, доверие и качество перевода.

Такой подход объединяет практики decision support, где отдельно оценивают
информированность, ясность и поддержку решения, и UX-подход, где результат
зависит от эффективности, эффективности использования и удовлетворённости в
конкретном контексте. Это перенос структуры из других доменов на финтех, а не
готовая валидированная «шкала agency». [AHRQ: decision-support measures](https://www.ahrq.gov/sdm/measures-data-funding/index.html),
[ISO 9241-110](https://www.iso.org/obp/ui?_escaped_fragment_=iso:std:iso:9241:-110:dis:ed-2:v1:en)

## Что именно измеряем

| Слой | Вопрос | Метрика | Зачем |
| --- | --- | --- | --- |
| Понимание | Верно ли клиент понял смысл hook? | Доля верных ответов на 3 comprehension-вопроса. | Не допускает, чтобы рост конверсии был результатом ложного обещания. |
| Agency в моменте | Чувствует ли клиент, что выбор остаётся за ним? | `Agency pulse` — средний балл 4 коротких утверждений. | Ближайшая прокси «возможности принять решение». |
| Способность действовать | Может ли клиент завершить нужный перевод без помех? | Completion rate, time-to-complete, early exit, use error. | Проверяет, что hook не ломает срочный путь. |
| Причинный эффект | Изменил ли hook outcome сверх естественного намерения? | Delta completed transfers / net volume в treatment vs holdout. | Отделяет эффект продукта от самоотбора. |
| Исполнение и доверие | Не навредило ли решение условиям и клиенту? | Quote/spread, repricing, failures, opt-out, жалобы. | Это обязательные guardrails, а не вторичные KPI. |

## 1. Мера понимания — обязательна до пилота

В concept/UX-тесте показывайте сильный frame, слабый frame и срочный сценарий.
После каждого — не подсказывая правильный ответ — спросите:

1. «Что означает эта карточка?»
2. «Гарантирует ли она, что перевод сейчас будет выгоднее?»
3. «Можно ли прямо сейчас выполнить обычный перевод, если деньги нужны срочно?»

**Метрика:** `comprehension pass rate` — доля участников, которые одновременно
ответили: «это контекст текущих условий», «нет» и «да». Ошибка понимания —
причина менять copy или интерфейс, а не оптимизировать конверсию.

## 2. Agency pulse — короткая продуктовая прокси

Сразу после решения или на небольшой случайной подвыборке после экрана просите
оценить по шкале 1–5 согласие с четырьмя утверждениями:

- «Мне понятно, какие условия перевода доступны сейчас».
- «Я сам(а) решаю, переводить ли сейчас».
- «Если перевод нужен срочно, я могу выполнить его без задержки».
- «Я понимаю, что карточка не обещает будущую выгоду».

`Agency pulse = среднее четырёх ответов`; сравнивайте среднее и распределение
между treatment и control. Обязательно оставляйте вариант «не хочу отвечать» и
не используйте ответы для персонализации или оценки клиента.

Это **не валидированная шкала**, а узкая операция-специфичная мера. Она
осмысленно опирается на измеряемые конструкты decision support — informedness,
ясность и поддержка — и на финансовую self-efficacy/skill, где спрашивают,
может ли человек принять сложное финансовое решение и распознать нехватку
информации. [AHRQ](https://www.ahrq.gov/sdm/measures-data-funding/index.html),
[CFPB Financial Skill guide](https://files.consumerfinance.gov/f/documents/bcfp_financial-well-being_measuring-financial-skill_guide.pdf)

**Важно:** не используйте 10-item CFPB Financial Well-Being Scale как KPI этого
экрана. Она валидирована для более широких финансовых security и freedom of
choice, а не для минутного решения о переводе. Её можно взять как долгосрочный
исследовательский outcome только для добровольной когорты и с отдельным
исследовательским дизайном. [CFPB guide](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/)

## 3. Главный эксперимент: не A/B по кликам, а holdout по eligible frame

### Кого рандомизировать

Единица эксперимента — **операция или сессия**, для которой одновременно:

- market model выдала `strong frame`;
- execution gate подтвердил quote;
- операция отвечает политикам частоты и комплаенса.

Такие случаи случайно распределяются:

- **Treatment:** обычный перевод + factual hook.
- **Control:** тот же обычный перевод и тот же quote, но без hook.

Рандомизировать нужно после eligibility и до показа интерфейса. Не сравнивайте
тех, кто сам открыл push, с теми, кто не открыл: это смешивает эффект hook с
изначальным намерением.

### Primary metric

Выберите один заранее зарегистрированный OEC:

```text
Incremental completed-transfer rate
= P(завершён перевод в заданном окне | treatment, eligible)
  − P(завершён перевод в заданном окне | control, eligible)
```

Рекомендуемое окно: сначала `same session` и `24 часа` как два раздельно
подписанных outcome. Не склеивайте их post hoc. `Net completed RUB volume` —
вторичная бизнес-метрика; CTR и открытие quote — только диагностика воронки.

Рандомизированные controlled experiments считаются способом установить
причинный эффект фичи на поведение; при этом краткосрочная метрика не всегда
предсказывает долгосрочную ценность, поэтому OEC и guardrails надо определить
до старта. [Microsoft Research: Online Experimentation](https://www.microsoft.com/en-us/research/publication/online-experimentation-at-microsoft/),
[Pitfalls of Long-Term Experiments](https://www.microsoft.com/en-us/research/publication/pitfalls-of-long-term-online-controlled-experiments/)

## 4. Поведенческие и UX-метрики

| Метрика | Формула / наблюдение | Интерпретация |
| --- | --- | --- |
| Ordinary-path completion | Завершённые переводы / eligible sessions. | Основной outcome, только как delta T–C. |
| Time to completion | Медиана времени от показа формы до подтверждения. | Рост в срочном сценарии — сигнал трения, не «вовлечения». |
| Early exit | Выход до подтверждения / eligible sessions. | Guardrail против перегрузки и сомнений. |
| Use error | Ошибки в форме, возвраты, повторная смена метода/страны. | Показатель того, что UI мешает выполнить задачу. |
| Hook open / CTR | Открытия карточки / показы. | Диагностика заметности; не мера ценности и не primary metric. |
| Follow-up confidence | Опциональный ответ через 24 ч: «Я считаю, что принял(а) подходящее для себя решение». | Exploratory; не доказывает финансовую выгоду. |

Разделяйте отчёт минимум на `срочный` и `допустимое окно`. Контекст задачи влияет
на UX-результат; стандарт определяет usability через конкретных пользователей,
цели и контекст использования, а не как универсальное свойство экрана.
[ISO 9241-110](https://www.iso.org/obp/ui?_escaped_fragment_=iso:std:iso:9241:-110:dis:ed-2:v1:en)

## 5. Необходимые guardrails

Эксперимент не считается успешным при положительном primary metric, если хотя бы
один заранее согласованный guardrail ухудшается сверх допустимого порога.

| Область | Что мониторим |
| --- | --- |
| Исполнимый quote | Recipient amount / effective spread относительно corridor-size-time baseline; reprice rate. |
| Ликвидность и операции | Отказы, route failures, задержки, лимитные срабатывания, концентрация спроса по коридору. |
| Клиентский вред | Opt-out, скрытие коммуникаций, жалобы, обращения в поддержку, тексты «мне пообещали выгоду». |
| Свобода действия | Completion и early exit в срочном сценарии не хуже control. |
| Модельная дисциплина | Частота frame, кластеризация, доля frame, не прошедших execution gate. |

Для каждого guardrail до пилота нужны: baseline, допустимый порог, владелец
метрики и действие при срабатывании (`pause hook`, снизить frequency cap,
отключить corridor). Без этого нельзя компенсировать вред ростом объёма.

## Минимальная схема событий

```text
frame_scored {corridor, rule_version, score_bucket, available_at}
  → execution_gate {eligible, reason, quote_id, spread_bucket}
  → experiment_assigned {unit_id, arm}
  → quote_shown {quote_id, hook_shown, copy_version}
  → hook_opened (optional)
  → transfer_started / transfer_completed / transfer_failed
  → quote_repriced / support_contact / opt_out
  → agency_pulse_submitted (optional, consented)
```

Не пишите в аналитический контур текст реквизитов, получателя или другие
платёжные персональные данные. Для анализа достаточно технических ID, времени,
коридора, bucket-ов и outcome.

## Решение по результату пилота

- **Идём дальше:** comprehension проходит заданный порог, `Agency pulse` не
  хуже control, primary metric положителен с заранее определённой статистической
  неопределённостью, guardrails в норме.
- **Дорабатываем:** понимание/agency нейтральны, но есть трение или слабая
  заметность; меняем copy/UI и повторяем эксперимент.
- **Останавливаем hook:** execution gate не подтверждает frame, ухудшается
  client quote/срочный путь или растут сигналы вреда — даже при высоком CTR.

## Практический вывод для текущего проекта

Вашей главной метрикой на первом пилоте должна стать **инкрементальная доля
завершённых переводов среди eligible сильных frames**, а не «клиентская
возможность» как расплывчатый KPI. Саму возможность измеряйте как защитный
product outcome: comprehension + `Agency pulse` + отсутствие деградации
срочного пути. Это честнее, измеримее и не заставляет выдавать интерес к hook
за пользу клиенту.

## Источники

- [CFPB — Financial Well-Being Scale](https://www.consumerfinance.gov/data-research/research-reports/financial-well-being-scale/), обновлено 2023.
- [CFPB — Measuring Financial Skill](https://files.consumerfinance.gov/f/documents/bcfp_financial-well-being_measuring-financial-skill_guide.pdf), 2018.
- [AHRQ — Measures for Shared Decision Making](https://www.ahrq.gov/sdm/measures-data-funding/index.html), доступ 2026-09-04.
- [ISO 9241-110 — interaction principles and usability definitions](https://www.iso.org/obp/ui?_escaped_fragment_=iso:std:iso:9241:-110:dis:ed-2:v1:en), доступ 2026-09-04.
- [Kohavi et al. — Online Experimentation at Microsoft](https://www.microsoft.com/en-us/research/publication/online-experimentation-at-microsoft/), 2009.
- [Dmitriev et al. — Pitfalls of Long-Term Online Controlled Experiments](https://www.microsoft.com/en-us/research/publication/pitfalls-of-long-term-online-controlled-experiments/), 2016.
