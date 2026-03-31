# Releasing

`plugin-crosswalk` publishes to PyPI via GitHub Actions Trusted Publishing.

## One-time PyPI setup

Before the first release, create a pending publisher on PyPI:

1. Go to [PyPI publishing settings](https://pypi.org/manage/account/publishing/).
2. Add a GitHub trusted publisher for:
   - PyPI project name: `plugin-crosswalk`
   - Owner: `MaxGhenis`
   - Repository: `plugin-crosswalk`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`

Important:

- PyPI does not reserve the name until the first successful publish.
- The first successful publish will create the project automatically.

## GitHub environment

The release workflow uses the `pypi` GitHub environment. Manual approval is
recommended before each publish.

## Cutting a release

1. Update `version` in `pyproject.toml`.
2. Commit the version change.
3. Create and push a tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

4. Approve the `pypi` environment deployment in GitHub Actions.
5. Optionally create a GitHub Release for the tag:

```bash
gh release create v0.1.0 --generate-notes
```

## Local verification

```bash
uv run pytest
uv build
```
