# Contributing

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
uv run --extra=redis --extra=rabbitmq --extra=celery pytest
```
