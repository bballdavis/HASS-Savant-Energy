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

## Capture real Home Assistant images

Documentation images must come from the actual Home Assistant interface and installed companion card. The previous mock interface and capture harness have been removed.

- Open the real companion breaker board and capture its desktop grid, standard mobile layout, ultra-compact mobile layout, and scene editor as needed. Firefox responsive mode can render a narrow viewport without editing the dashboard configuration.
- Change display/navigation state only. Do not toggle a relay, activate a scene, create/delete scene data, or save dashboard changes for a screenshot.
- Capture setup through the real **Reconfigure** flow. Pause before entering credentials; never include passwords, tokens, private keys, browser tabs, account details, or unrelated dashboards.
- Crop the capture to the relevant card or form. Keep the interface text, measurements, and controls intact; do not recreate them, generate replacement UI, or substitute synthetic values.
- Keep raw captures outside the public repository. Commit only reviewed excerpts and record their origin, viewport, and cropping in `docs/assets/provenance.json`.

The breaker board is built from [Savant-Card](https://github.com/bballdavis/Savant-Card) and bundled with this integration. See [companion builds](companion-build.md) for provenance and update PRs. The old `savant-energy-scenes-card` type now aliases the new board. Screenshots show the installed interface at capture time, not live release acceptance evidence.

## GitHub Pages rollout

Pull requests and pushes to `dev`/`main` build and validate the site. Production deployment runs only on `main`, using GitHub Pages artifacts and the `github-pages` environment. Review the build artifact before merging. The configured public address is:

```text
https://bballdavis.github.io/HASS-Savant-Energy/
```

Repository **Settings → Pages → Build and deployment → Source** must use **GitHub Actions**. A missing Pages API result does not prove configuration; confirm it before rollout. No custom domain is configured.

After merge, verify homepage, installation, Legacy, generated reference, images, search, and direct deep links on the public URL. Only after the site is live, update `custom_components/savant_energy/manifest.json`’s `documentation` URL to the public site in a follow-up change. The branch deliberately retains the existing URL until that verification is possible.

For failures, inspect the Actions build/deploy logs. Revert the faulty documentation commit on `main` and let the same workflow republish the previous content. For card regressions, revert the companion pin and its artifacts together; documentation-only rollbacks do not change the runtime.
