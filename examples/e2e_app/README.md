# e2e_app — real-Azure certification app

This app exists **only** for the release gate. The `e2e-azure` GitHub workflow
deploys it to a temporary Azure Functions Consumption (Y1) host, runs
`tests/e2e` against it, records an `azure-cert` artifact, then deletes the
resource group.

It differs from the user-facing examples (e.g. `examples/custom_provider.py`) in
two ways:

1. **Candidate under test.** `requirements.txt` does not pin
   `azure-functions-knowledge`. The workflow builds a wheel from the release
   commit, drops it in `wheels/`, and appends the local wheel path so the
   deployed host runs the exact source being certified (not the PyPI release).
2. **Deterministic, secret-free provider.** It registers a single in-memory
   `StaticProvider` (two fixed documents, no external service) so the live
   assertions are stable. Crucially, `StaticProvider.__init__` **raises** unless
   the resolved `%STATIC_CONNECTION%` value equals `static-e2e`, so the
   certification also proves `%VAR%` connection-string substitution ran on the
   worker.

## Routes (all `AuthLevel.ANONYMOUS`)

| Route | Decorator | Proves |
| --- | --- | --- |
| `GET /api/health` | plain | import-time `register_provider` (lists `"static"`) |
| `GET /api/search?q=<term>` | `@kb.input` | provider search + result injection + `%VAR%` resolution |
| `GET /api/doc/{id}` | `@kb.inject_client` | imperative client access + `%VAR%` resolution |

## Reproducing locally

The workflow sets the `STATIC_CONNECTION=static-e2e` app setting after deploy.
To run locally you must mirror that:

```bash
# 1. Build a candidate wheel from the repo root and drop it in wheels/
python -m build --wheel --outdir dist
cp dist/azure_functions_knowledge-*.whl examples/e2e_app/wheels/
echo "./wheels/$(basename dist/azure_functions_knowledge-*.whl)" >> examples/e2e_app/requirements.txt

# 2. Provide the resolved connection value and start the host
cd examples/e2e_app
STATIC_CONNECTION=static-e2e func start
```
