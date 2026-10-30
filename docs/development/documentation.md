---
title: Documentation workflow
---

# Maintain the documentation

Canonical guides live in `docs/`. The Docusaurus Classic TypeScript application lives in `website/` and reads those same files. The README stays a short showcase, with links to complete guides. Historical release notes stay clearly labeled.

## Local setup

Use Node 22 or later and Python 3.9 or later. From the repository root:

```bash
cd website
npm ci
python3 -m venv .venv-docs
.venv-docs/bin/python3 -m pip install -r requirements-docs.txt
npm start
```

On Windows, use `.venv-docs\Scripts\python.exe` for the pip command. The scripts detect this local environment; alternatively install requirements in your active Python environment and set `PYTHON` to its interpreter.

## Generate and validate

```bash
npm run docs:generate
npm run docs:check
npm run docs:test
npm run typecheck
npm run build
npm run links:check
npm run serve
```

Commit generated Markdown along with its source changes. `docs:check` compares expected content without writing files. CI runs it before the build so generation cannot hide a stale committed reference.

The generator parses Python syntax with `ast`, reads English JSON labels, and parses service YAML. It never imports Home Assistant or executes integration modules. It compares service fields and required flags with `api.py`, extracts option defaults and supported validators from `config_flow.py`/`const.py`, and fails on unsupported option/service schema changes. Labels retained for compatibility are distinguished from offered forms. Generated labels are reference, not a setup sequence.

Examples and behavioral explanations, especially REST limitations, need human/source review when runtime behavior changes; static field extraction does not prove runtime correctness.

## Reproduce demo images

Documentation images are original illustrative browser renders, not live Home Assistant captures. Fixtures use synthetic devices, readings, and reserved documentation IP addresses. No credentials or live hardware are needed.

```bash
npx playwright install chromium
npm run demo:capture
```

For an interactive local preview:

```bash
npm run demo:serve
```

Open `http://127.0.0.1:4174/?view=setup` (or `overview`, `entities`, `energy`, `scenes`, `options`). The isolated capture server exposes only demo files and the integration’s public English labels. Capture blocks non-local requests. Edit `website/demo/fixtures.json` and the mock layout to update examples. Do not present these images as proof of live integration behavior. Source/provenance is recorded beside the images.

## GitHub Pages rollout

Pull requests and pushes to `dev`/`main` build and validate the site. Production deployment runs only on `main`, using GitHub Pages artifacts and the `github-pages` environment. Review the build artifact before merging. The configured public address is:

```text
https://bballdavis.github.io/HASS-Savant-Energy/
```

Repository **Settings → Pages → Build and deployment → Source** must use **GitHub Actions**. A missing Pages API result does not prove configuration; confirm it before rollout. No custom domain is configured.

After merge, verify homepage, installation, Legacy, generated reference, images, search, and direct deep links on the public URL. Only after the site is live, update `custom_components/savant_energy/manifest.json`’s `documentation` URL to the public site in a follow-up change. The branch deliberately retains the existing URL until that verification is possible.

For failures, inspect the Actions build/deploy logs. Revert the faulty documentation commit on `main` and let the same workflow republish the previous content. No integration runtime rollback is required for documentation-only changes.
