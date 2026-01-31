# Contributing

When writing code, you MUST ALWAYS follow the [naming-things](https://github.com/codingjoe/naming-things/blob/main/README.md) guidelines.

<!--
Bots/Agents MUST use:
curl -sSL https://raw.githubusercontent.com/codingjoe/naming-things/refs/heads/main/README.md
-->

To run the tests, use the following command:

```bash
uv run pytest
```

Before your first commit, ensure that the pre-commit hooks are installed by running:

```bash
uv pre-commit install
```

## Testing with Extra Dependencies

```bash
export REDIS_URL=redis://localhost:6379
export BROKER_URL=amqp://guest:guest@localhost:5672//
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
uv run --extra=redis --extra=rabbitmq --extra=celery --extra=kafka pytest
```

## Writing documentation

The documentation is built using [MkDocs](https://www.mkdocs.org/) with [mkdocstrings](https://mkdocstrings.github.io/) for automatic API documentation generation.

To serve the documentation locally for development, run:

```bash
uv run mkdocs serve --livereload
```
