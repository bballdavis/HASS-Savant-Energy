---
title: Companion build and updates
---

# Ship a reviewed companion build

The integration vendors a tested build from [bballdavis/Savant-Card](https://github.com/bballdavis/Savant-Card). Users receive it with the integration; Home Assistant does not fetch or build frontend code at runtime.

`custom_components/savant_energy/www/bundle.json` records the full upstream commit, package version, original build hash, shipped file hashes, and small packaging adaptations. The MIT license and upstream dependency notices remain with the artifact. `card_version.py` gives browsers a content-derived cache version. The old scenes-only file is replaced by a compatibility alias.

## Automatic update proposals

Every push into integration `main` runs **Check upstream companion updates**. It can also be run manually on `main`.

1. Compare upstream `main` with the committed pin. Equal revisions and an upstream ancestor of the pin keep the existing build, including a fix pinned before its upstream merge.
2. For a potential update, run `npm ci` and the upstream `npm run check` (lint, tests, TypeScript, build) in a job without write credentials.
3. Compare the built runtime hash. If unchanged, keep the existing artifact. Otherwise import it and validate compatibility and provenance.
4. A separate job opens or refreshes one PR from `upstream/companion-card` into `main`. It changes only the bundled files and cache constant. It never merges automatically.

A failed build stops the proposal and leaves the existing pin in use. Diverged or squash-merged history can produce a reviewable proposal; it is not accepted automatically. Upstream package versions alone are insufficient because the source currently reuses `0.1.0`.

Repository **Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests** must permit PR creation. This workflow requests contents/PR write permission only in the proposal job. If policy blocks it, review the workflow error and enable PR creation or open the pushed branch manually. No personal token is required.

GitHub may hold checks on token-created PRs for approval; use **Approve workflows to run** in the PR before merging. See [GitHub’s workflow trigger behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow). A reviewed merge is required before the new artifact becomes part of main or a later integration release.

## Manual import and verification

Use Node 22 and Python 3.12. Clone upstream into a directory named `Savant-Card` (its HACS tests check that name), check out a reviewed full commit, then:

```bash
# In the upstream Savant-Card checkout
npm ci
npm run check

# In this integration repository
python3 tools/bundle_companion.py --source /path/to/Savant-Card
python3 tools/bundle_companion.py --check
node tools/test_companion.mjs /path/to/Savant-Card
python3 -m unittest discover -s tests
```

Integration tests need `aiohttp==3.13.2` and `paramiko==3.5.1` in the test environment; Home Assistant imports are stubbed. The integration’s **Companion card** CI independently rebuilds the exact pinned revision, compares committed output, and checks duplicate loads, HACS ownership, legacy YAML, the editor, and rendering without hardware writes.

The importer rejects unknown packaging such as external module imports. Review packaging changes instead of bypassing that check. Keep explanations and screenshots reviewed separately: a build proves neither live hardware behavior nor a new frontend’s visual correctness.
