# Demo Communication Library

All entries are for a **demo UI scenario** linked to a retained public-source snapshot; they are not live market assessments, execution quotes, forecasts, or financial advice.

## Allowed UI text

| Scenario | Push / screen wording | Why it is allowed |
|---|---|---|
| `current` | «Демо-сценарий для перевода в Таджикистан. Откройте, чтобы посмотреть статус публичного ориентира.» | Describes the scenario and action, not a benefit or prediction. |
| `current` | «Сигнал всё ещё актуален. Можно рассмотреть перевод, если срок позволяет.» | Distinguishes the only scenario where the user may inspect the normal path without claiming an execution outcome. |
| `changed` | «Пуш устарел. Не делаем вывод о текущих условиях по старому пушу.» | Clearly suppresses the original claim and offers neutral continuation. |
| `unknown` | «Не удалось проверить статус. Мы не знаем, сохранился ли контекст из пуша.» | Explains uncertainty rather than hiding it; ordinary transfer remains available. |
| Urgent route | «Нужно перевести сейчас? Продолжите обычный перевод.» | Preserves agency and does not judge the decision. |
| Simulation | «Перевод создан в режиме симуляции. Деньги не списывались и не отправлялись.» | States the PoC boundary plainly. |

## Prohibited wording

| Prohibited example | Why it is prohibited |
|---|---|
| «Сейчас выгодно переводить» | Presents a public fixture as a current individual recommendation. |
| «Успейте, пока не подорожало» | Predicts future movement and pressures action. |
| «Вы сэкономите 500 ₽» | Promises an exact outcome without an execution quote. |
| «Лучший курс гарантирован» | Guarantee and unsupported execution claim. |
| «Ваши близкие получат больше» | Personalised, emotionally pressuring claim unsupported by the public reference. |
| «Курс в приложении такой-то» | Confuses a public analytical reference with a bank execution rate. |

## Review rule

Every new fixture, push, screen, and simulated result is checked against this library. If freshness is unavailable, use only the `unknown` wording and preserve the ordinary-transfer action.
