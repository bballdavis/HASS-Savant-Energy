---
title: Contributing
---

# Contribute to the project

Report bugs and propose changes through [GitHub issues](https://github.com/bballdavis/HASS-Savant-Energy/issues) and pull requests. Describe the user-visible problem, expected behavior, versions, and relevant validation.

## Documentation changes

Edit canonical Markdown in `docs/`. Use short task-oriented guides, explicit prerequisites, expected results, and links to deeper reference. Follow [the documentation workflow](documentation.md) to regenerate source-backed reference and check the site.

## Integration changes

Keep stable identity, source availability, and relay targeting separate. Test behavior against the relevant existing tests; do not call a telemetry fix live-verified from unit tests alone. Read [architecture](../current-api-workflow.md) and [live diagnostics](../live-diagnostics.md) before working on connection or discovery behavior.

```bash
python3 -m unittest discover -s tests
```

Tests can require additional development dependencies appropriate to the affected module. Existing diagnostic tools have their own requirements under `tools/`.

## Review expectations

Explain the final behavior and the tests actually performed. Use synthetic fixtures in public examples and remove credentials/identifiers from issue attachments. This project uses AI coding assistance; claims and changes still require review and appropriate verification.

The project is licensed under GNU GPL v3; see [LICENSE](https://github.com/bballdavis/HASS-Savant-Energy/blob/main/LICENSE).
