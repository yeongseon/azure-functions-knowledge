# Testing

How to run the test suite and how to test handlers that use knowledge bindings.

## Running the suite

```bash
make install        # set up the dev environment
make test           # run pytest with coverage
```

Or directly with hatch:

```bash
hatch run pytest --cov --cov-report=term-missing -q
```

The project enforces a **95% coverage floor**; changes that drop below it must
add tests to compensate.

## Full local check

Mirror CI before opening a PR:

```bash
make lint        # ruff
make typecheck   # mypy
make test        # pytest + coverage
make build       # build the distribution
```

## Testing your handlers

Because `input`/`inject_client` create the provider through the registry, the
cleanest way to test a handler is to register a fake provider:

```python
from azure_functions_knowledge import Document, register_provider

class FakeProvider:
    def __init__(self, *, connection, **kwargs):
        pass

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        return [Document(
            document_id="1", content="hello", title="Doc",
            url="https://example.test/1", source="fake",
        )]

    def get_document(self, document_id: str) -> Document:
        return Document(
            document_id=document_id, content="hello", title="Doc",
            url="https://example.test/1", source="fake",
        )

    def close(self) -> None:
        pass

register_provider("fake", FakeProvider)
```

Then decorate a handler with `provider="fake"` and call it directly. No network
access or Notion token is required.

## CI environment

The `ci-test.yml` workflow runs the same lint / typecheck / test steps across
the supported Python versions and uploads coverage. No secrets are required to
run the suite because the built-in tests do not hit the live Notion API.
