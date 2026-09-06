# Радар выгодного момента — demo web

В этой папке лежит весь отдельный веб-демо: интерфейс, данные для графика,
шаблоны push и генератор данных из canonical golden labels.

Запуск из корня репозитория:

```bash
python3 -m http.server 8080 --directory demo-web
```

Открыть: `http://localhost:8080`.

Обновить данные после пересборки `golden_labels.parquet`:

```bash
python3 demo-web/tools/generate_demo_data.py
```
