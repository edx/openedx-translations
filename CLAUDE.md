# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Does

This is the central translation coordination hub for edX. It:
- Stores English translation source files (.po and .json) extracted daily from 50+ Open edX repositories
- Requests translations from the [ai-translations](github.com/edx/ai-translations) service.
- Validates translation files on pull requests
- Maintains separate branches for versioned releases (e.g., `open-release/redwood.master`)
- Automates translations PR management

The `translations/` directory contains locale files organized by upstream repository (e.g., `translations/frontend-app-learning/`, `translations/edx-platform/`). These files are largely auto-generated — PRs touching `.po` or `.json` files under `translations/` come from either the ai-translations service (JavaScript apps) or the Transifex GitHub App (Python apps, still active during migration).

## Commands

### Python Setup
```bash
make translations_scripts_requirements  # Install translation script deps
make test_requirements                  # Install test deps (pytest, pytest-cov, responses)
```

### Running Tests
```bash
make test                               # Full suite with coverage
pytest -v -s scripts/tests/test_validate_translation_files.py  # Single test file
pytest -v -s scripts/tests/test_validate_translation_files.py::TestClassName::test_method  # Single test
```

### Translation Validation
```bash
make validate_translation_files         # Validate .po and .json files
```

### Transifex Resource Name Management (legacy Python track)
```bash
make fix_transifex_resource_names RELEASE=<release-name>      # Fix resource names
make fix_dry_run_transifex_resource_names RELEASE=<release-name>  # Dry run
```

### Dependency Management
```bash
make upgrade                            # Recompile requirements/*.txt from *.in files
```

## Architecture

### Key Scripts (`scripts/`)

- **`validate_translation_files.py`** — Validates `.po` and `.json` translation files for syntax errors and encoding issues. Called by CI on PRs.
- **`fix_transifex_resource_names.py`** — Renames auto-generated Transifex resource slugs to human-readable names using the Transifex API. (Transifex track only.)
- **`release_project_sync.py`** — Syncs the main Transifex project resources/languages to versioned release projects. (Transifex track only.)

### GitHub Actions Workflows (`.github/workflows/`)

The repo is currently in a **hybrid state**: JavaScript/frontend apps use ai-translations; Python/Django apps still use Transifex.

Workflows use `dorny/paths-filter` to conditionally skip expensive steps when only `.po` files changed.

#### Translation workflows

- **`extract-translation-source-files.yml`** — Daily cron; clones ~50 upstream repos (including `ai-translations`) and extracts English source strings into `translations/`.
- **`translate-source-strings.yml`** — Calls the ai-translations service API to fetch translated strings for JavaScript frontend apps (~22 apps, ~21 languages).
- **`seed-translations.yml`** — Seeds/trains the ai-translations service with source strings.

These 3 jobs authenticate using `EDX_TRANSLATIONS_PROD_CLIENT_ID/SECRET` and an LMS JWT token.

#### Validation workflows

- **`validate-translation-files.yml`** — PR check; runs `validate_translation_files.py` for modified `.po` and `.json` files.
- **`python-tests.yml`** — Runs pytest when non-`.po` files change (skips on pure translation file PRs).

#### Cleanup & merge workflows

- **`automerge-transifex-app-prs.yml`** — Auto-merges bot PRs from the Transifex GitHub App (Python app translations, still active).
- **`fix-transifex-resource-names.yml`** / **`release-project-sync.yml`** — Transifex resource management for Python apps and release branches.

### JavaScript App Configuration (`.github/translations-config.json`)

All JavaScript apps are registered in `javascriptApplications`. Each entry is keyed by repo name with an optional config object supporting these fields:

- **`owner`** — GitHub org (defaults to `edx`)
- **`pathOverride`** — overrides the default `src/i18n` path for source/translated files; only supported for non-monorepo apps (monorepo subpackages always use `packages/<package>/src/i18n`)
- **`subpackages`** — list of package directory names inside a monorepo's `packages/` directory; presence of this key marks the repo as a monorepo

Apps **with** `subpackages` are treated as monorepos throughout the extract, seed, and translate workflows. They are split into a separate matrix from regular JS apps. Each subpackage is treated as its own translation unit, with:
- Source strings at `translations/<repo>/packages/<package>/src/i18n/transifex_input.json`
- Translated strings at `translations/<repo>/packages/<package>/src/i18n/messages/<repoLang>.json`
- `application_name` of `<repo>/<package>` (e.g., `frontend-plugins/cohesion-wrapper`) when calling the ai-translations API

### Translation Provider Configuration

- **`transifex.yml`** — Defines all 50+ upstream repositories, file path patterns, and language settings for the Transifex integration. Still active for the Python app translation track.
- The connection to `ai-translations` is configured via GitHub variables in the repo using:
    - `AI_TRANSLATIONS_FETCH_TRANSLATIONS_URL`
    - `AI_TRANSLATIONS_SEED_TRANSLATIONS_URL`

## Environment Requirements

- **Python 3.11**
- **Node.js 20** (`.nvmrc`) — used only for `@formatjs/cli` JSON translation validation
- No virtual environment is pre-configured; set one up manually or use the CI approach
