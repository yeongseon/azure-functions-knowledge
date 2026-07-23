# Release Process

This document outlines the steps to release a new version of **azure-functions-knowledge-python** to PyPI and update the changelog using the existing Makefile and Hatch-based workflows.

---

## Step 1: Bump Version and Generate Changelog

Use Makefile targets to bump the version and update the changelog:

```bash
make release-patch     # Patch release (e.g., v0.10.0 -> v0.10.1)
make release-minor     # Minor release (e.g., v0.10.1 -> v0.11.0)
make release-major     # Major release (e.g., v0.11.0 -> v1.0.0)
```

Each command will:

1. Update the version in `src/azure_functions_knowledge/__init__.py`
2. Generate or update `CHANGELOG.md` via `git-cliff`
3. Commit the version bump and changelog
4. Create a Git tag (e.g., `v0.11.0`) and push to `main`

> Make sure your `main` branch is up-to-date before running these commands.

---

## Changelog Generation

The changelog is generated automatically by [git-cliff](https://git-cliff.org/) from conventional commit messages.

### Configuration

- `cliff.toml` - defines commit grouping, categories, and output format
- `Makefile` - `make changelog` runs `git-cliff -o CHANGELOG.md`

### Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/) for proper changelog grouping:

| Prefix | Changelog Category |
|--------|--------------------|
| `feat:` | Features |
| `fix:` | Bug Fixes |
| `docs:` | Documentation |
| `refactor:` | Refactor |
| `style:` | Styling |
| `test:` | Testing |
| `perf:` | Performance |
| `ci:` / `chore:` | Miscellaneous Tasks |
| `build:` | Other |

Use scopes for more context: `fix(openapi): preserve explicit 200 response`

### Manual Changelog Regeneration

```bash
make changelog           # Regenerate CHANGELOG.md from all tags
make commit-changelog    # Stage and commit the updated changelog
```

---

## Step 2: Build and Test the Package

```bash
make build
```

To test the local build:

```bash
pip install dist/azure_functions_knowledge-<version>-py3-none-any.whl
```

---

## Step 3: Publish to PyPI (GitHub Actions, primary)

The `.github/workflows/publish-pypi.yml` workflow builds and uploads the distribution to PyPI on every `v*` tag push (or on demand via `workflow_dispatch`). It uses [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/) over OIDC, so no PyPI API token is stored as a secret.

Pushing a release tag (produced by the `make release-*` targets in Step 1) is therefore all that is normally required to publish.

### Trusted publisher configuration

PyPI authorizes the upload by matching the OIDC claims presented by GitHub Actions against a trusted publisher registered on the PyPI project. The PyPI publisher config must use these exact values:

| Field on PyPI publisher form | Value |
| --- | --- |
| PyPI project | `azure-functions-knowledge` |
| Owner | `yeongseon` |
| Repository name | `azure-functions-knowledge-python` |
| Workflow filename | `publish-pypi.yml` |
| Environment name | `pypi` |

Notes:

- **Workflow filename** is the file under `.github/workflows/` (`publish-pypi.yml`), **not** the workflow display name (`Publish to PyPI`). Entering the display name will not match.
- **Repository name** is the GitHub repository slug (`azure-functions-knowledge-python` with the `-python` suffix from the toolkit-wide rename), not the PyPI project name (`azure-functions-knowledge`) and not the Python import name (`azure_functions_knowledge`).
- **Environment name** matches `environment: pypi` declared on the `build-and-publish` job in the workflow. Renaming that environment requires updating the PyPI publisher record.
- Enter all values exactly as shown; mismatches in repository name, workflow filename, environment, or project name will cause `invalid-publisher` at upload time.

To register the publisher on PyPI:

- If the PyPI project `azure-functions-knowledge` already exists, open the project page on PyPI → **Manage** → **Publishing** → **Add a new publisher** and enter the values above.
- If the PyPI project does not exist yet (first release), register a **pending publisher** under the maintainer's PyPI account with the same values; the first successful upload will then create the project. A pending publisher does **not** reserve the project name on PyPI — anyone else can still register the project before the first publish, so cut the first release promptly.

### Re-run a failed publish

After updating the trusted publisher in PyPI, the existing tag can be re-published without cutting a new version:

- From the GitHub Actions UI, open the failed `Publish to PyPI` run and click **Re-run failed jobs**, or
- Trigger the workflow via `workflow_dispatch` with the existing tag as input (for example `v0.1.0`); the workflow checks out that tag and republishes.

Confirm the run succeeds and the new version appears at `https://pypi.org/project/azure-functions-knowledge/`.

### Local fallback (manual)

Only needed if the GitHub Actions publish is unavailable; the OIDC workflow above is the supported path.

```bash
make publish-pypi
```

- Uses `hatch publish` under the hood
- Relies on `~/.pypirc` for authentication (must contain a PyPI token)
---

## Step 4: (Optional) Publish to TestPyPI

```bash
make publish-test
```

To install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ azure-functions-knowledge-python
```

---

## Summary of Makefile Commands

| Task | Command |
|------|---------|
| Version bump + changelog | `make release-patch` / `release-minor` / `release-major` |
| Build distributions | `make build` |
| Publish to PyPI | `make publish-pypi` |
| Publish to TestPyPI | `make publish-test` |
| Regenerate changelog only | `make changelog` |
| Show current version | `make version` |

---

## Related

- [CHANGELOG.md](https://github.com/yeongseon/azure-functions-knowledge-python/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/yeongseon/azure-functions-knowledge-python/blob/main/CONTRIBUTING.md)
- [PyPI Publishing with Hatch](https://hatch.pypa.io/latest/publishing/)
