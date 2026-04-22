# Savant Energy Agent Guide

This repository is a Home Assistant custom integration for Savant Energy hardware. Keep changes narrow, validate behavior against Home Assistant integration patterns, and prefer fixing the controlling code path over layering workarounds.

## Architecture

- `custom_components/savant_energy/__init__.py` owns config-entry setup, the `SavantEnergyCoordinator`, platform forwarding, and Lovelace resource registration.
- `custom_components/savant_energy/snapshot_data.py` is the TCP snapshot ingestion path. It connects to the Savant controller, decodes the base64 payload, and returns the JSON used to build entities.
- `custom_components/savant_energy/sensor.py`, `binary_sensor.py`, `switch.py`, and `button.py` materialize Home Assistant entities from `coordinator.data["snapshot_data"]["presentDemands"]`.
- `custom_components/savant_energy/utils.py` contains the DMX/OLA integration, address discovery, caches, retry loops, and shared API statistics.
- `custom_components/savant_energy/scene.py` and `api.py` handle scene storage, execution, REST endpoints, and HA services.
- `custom_components/savant_energy/savant-energy-scenes-card.js` is the custom frontend surface. Frontend regressions often come from REST shape changes or static resource registration in `__init__.py`.

## Development Rules

- Preserve stable Home Assistant identifiers. Device identifiers and entity `unique_id` values are based on the Savant `uid`; do not churn them unless migration is intentional.
- When changing entity behavior, inspect the coordinator data shape first. Most platform bugs trace back to missing or malformed `presentDemands` data rather than the entity class itself.
- Treat `utils.py` module globals as shared state. Cache changes, retry logic, or stat tracking can affect every integration instance.
- Keep scene changes compatible with both REST callers and service calls. The frontend card depends on the existing scene API contract.
- Prefer config-entry option fallbacks in the existing style: `entry.options.get(key, entry.data.get(key, default))`.
- When a live Home Assistant instance is available, use the workspace `home-assistant` MCP server before adding temporary debug code. Prefer reading current states, services, traces, logs, and entity metadata through MCP first.
- If the MCP server is relevant to the task, inspect `tools/ha-mcp-wrapper.ps1` and `.local/hass.env` before guessing at connection details.

## Debugging Workflow

- If entities are missing, inspect logs around coordinator refresh in `custom_components/savant_energy/__init__.py` and snapshot parsing in `custom_components/savant_energy/snapshot_data.py`.
- If DMX addresses stay unavailable, inspect the RDM discovery and UID lookup path in `custom_components/savant_energy/utils.py` before changing sensors or switches.
- If switch control fails, trace the DMX address source first. `switch.py` depends on the DMX address sensor state and then sends a full DMX payload.
- If scene behavior breaks, review both `custom_components/savant_energy/scene.py` and `custom_components/savant_energy/api.py`. Scene execution, storage normalization, REST responses, and service handlers are split across those files.
- If the custom card breaks, verify the static resource registration path and API responses before changing the JavaScript.
- If a live Home Assistant instance is available, prefer the workspace `home-assistant` MCP server for state inspection, service discovery, automation tracing, and log-oriented investigation before adding temporary debug code.
- Use `.local/hass-debug.ps1` only when the MCP server is unavailable or when you need a direct REST comparison.

## Change Strategy

- Make small edits and validate immediately.
- Prefer focused checks over whole-repo churn.
- Do not rewrite logging style or comments across unrelated files.
- Keep documentation in sync when changing setup, API shape, or developer workflow.

## Local-Only Files

- `.local/` is ignored and intended for machine-specific scripts, env files, and scratch notes.
- `AGENTS.local.md` is ignored and reserved for private instructions, tokens, or environment-specific debugging notes that should not be committed.

## Useful Local Setup

- Workspace MCP configuration lives in `.vscode/mcp.json`.
- The workspace MCP config launches `ha-mcp` through `tools/ha-mcp-wrapper.ps1`, which loads `.local/hass.env` and starts the upstream stdio server with the expected `HOMEASSISTANT_URL` and `HOMEASSISTANT_TOKEN` environment variables.
- Local Home Assistant connection details and helper scripts live under `.local/`.
- Use `.local/hass-debug.ps1` for quick API and error-log pulls when an MCP resource or tool is not enough.
- The wrapper intentionally uses `uvx --python 3.13 --refresh ha-mcp@latest`; keep the wrapper aligned with upstream `ha-mcp` documentation if the server contract changes.

## MCP Usage Expectations

- Prefer MCP when you need current Home Assistant state, service lists, config entries, traces, logs, or entity metadata.
- Prefer the repo wrapper instead of hand-crafting alternate local launch commands.
- If file editing or config management tools are needed from MCP, verify the Home Assistant-side `ha_mcp_tools` component and the required feature flags are installed and enabled.
- If you update the wrapper or MCP configuration, update [docs/development.md](docs/development.md) at the same time.
- The upstream `homeassistant-ai/ha-mcp` repository is the source of truth for tool names and command shapes. For logs and history, prefer `ha_get_logs` and `ha_get_history`; for execution tracing use `ha_get_automation_traces`; for service discovery use `ha_list_services`; for integration metadata use `ha_get_integration`.
- `ha_list_files` only lists `www/`, `themes/`, and `custom_templates/`; it does not enumerate a generic logs folder.
- For log-file inspection, prefer `ha_get_logs(source="system"|"error_log"|"supervisor")` first and `ha_read_file(path="home-assistant.log", tail_lines=...)` only when the file-access component is installed.

## Home Assistant MCP Guidance

- Keep `.local/hass.env` populated with the Home Assistant base URL and long-lived token before relying on the MCP server.
- Prefer MCP for runtime investigation that needs current HA state, integrations, services, automations, traces, or filesystem-backed HA MCP tools.
- Fall back to `.local/hass-debug.ps1` when the MCP server is unavailable or you need a direct REST response for comparison.
- If `ha-mcp` file tools are needed, ensure the Home Assistant side also has the `ha_mcp_tools` custom component and the required feature flags enabled.
