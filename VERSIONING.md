# Semantic Versioning

This project uses **semantic versioning** with automatic version management via [`setuptools_scm`](https://setuptools-scm.readthedocs.io/).

## Version Format

Versions follow `MAJOR.MINOR.PATCH`:

- **MAJOR** — Breaking changes (incompatible API changes)
- **MINOR** — New features (backward-compatible)
- **PATCH** — Bug fixes (backward-compatible)

## How It Works

`setuptools_scm` derives the package version from git history:

- **Tagged release**: `git tag v1.2.3` → version `1.2.3`
- **Between tags**: version becomes something like `1.2.4.dev5+g1234567`
- **No tags**: version `0.0.0.dev0`

## Creating a Release

1. Update `CHANGELOG.md` — move the relevant `[Unreleased]` items into a new `[X.Y.Z] - YYYY-MM-DD` section.
2. Commit the changelog change.
3. Tag the release:

   ```bash
   git tag v0.2.0      # MINOR — new feature
   git tag v0.1.1      # PATCH — bug fix
   git tag v1.0.0      # MAJOR — breaking change
   ```

4. Push the tag:

   ```bash
   git push origin main
   git push origin v0.2.0
   ```

5. GitHub Actions (`.github/workflows/release.yml`) builds and publishes to PyPI automatically on tag push.

## When to Bump Which Number

- **PATCH** — bug fixes, documentation updates, internal refactoring, test additions.
- **MINOR** — new tools, new optional parameters, new endpoint coverage, deprecating (not removing) features.
- **MAJOR** — removing tools, renaming tool parameters, breaking response shape changes, dropping Python versions.

## Pre-release Versions

For alpha/beta/release-candidate tags:

```bash
git tag v1.0.0-alpha.1
git tag v1.0.0-beta.1
git tag v1.0.0-rc.1
```

## Checking the Current Version

```bash
# From Python
python -c "import gitea_mcp; print(gitea_mcp.__version__)"

# From setuptools_scm directly
python -m setuptools_scm
```

## References

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [setuptools_scm](https://setuptools-scm.readthedocs.io/)
