# Development Guide

This repository uses a local Home Assistant MCP setup for day-to-day debugging and code review support. The goal is to inspect the live system first, then change the integration code only when the evidence points there.

## MCP Setup

The workspace MCP server is defined in [.vscode/mcp.json](../.vscode/mcp.json) and launches [tools/ha-mcp-wrapper.ps1](../tools/ha-mcp-wrapper.ps1).

The wrapper does three things:

1. Loads [.local/hass.env](../.local/hass.env) for machine-specific values.
2. Exports `HOMEASSISTANT_URL` and `HOMEASSISTANT_TOKEN` for the upstream `ha-mcp` server.
3. Starts `uvx --python 3.13 --refresh ha-mcp@latest` so VS Code can connect to Home Assistant through MCP.

Recommended `.local/hass.env` values:

```env
HOMEASSISTANT_URL=http://homeassistant.local:8123
HOMEASSISTANT_TOKEN=your_long_lived_access_token
FASTMCP_SHOW_SERVER_BANNER=false
```

Optional aliases for the direct REST helper:

```env
HASS_BASE_URL=http://homeassistant.local:8123
HASS_TOKEN=your_long_lived_access_token
```

## How To Use It

Use the MCP server first when you need current state from the Home Assistant instance.

Good MCP questions for this repo:

- What entities were created for the Savant integration?
- What state or attributes do the breaker switches and DMX sensors currently have?
- What services, traces, or logs explain why a scene or switch action failed?
- What config entry options are active for the integration?

When the MCP server is not available, use [.local/hass-debug.ps1](../.local/hass-debug.ps1) for direct REST checks against Home Assistant.

## MCP Quick Reference

The upstream tool names and behavior come from the `homeassistant-ai/ha-mcp` repository. For the latest authoritative list, check the upstream README and tool files in that repo before inventing new command names.

Common read-only tools that are useful for this integration:

- `ha_get_logs(source="logbook"|"system"|"error_log"|"supervisor", limit=?, search=?, hours_back=?, entity_id=?, end_time=?, offset=?, compact=?, level=?, slug=?)`
- `ha_get_history(entity_ids, source="history"|"statistics", start_time=?, end_time=?, limit=?, offset=?, minimal_response=?, significant_changes_only=?, period=?, statistic_types=?)`
- `ha_get_automation_traces(automation_id, run_id=?, limit=?, detailed=?)`
- `ha_get_integration(entry_id=?, query=?, domain=?, exact_match=?)`
- `ha_list_services(domain=?, query=?, limit=?, offset=?, detail_level=?)`
- `ha_get_state(entity_id?)` and `ha_search_entities(query=?, domain_filter=?, area_filter=?)` for state/entity lookups when available in the connected MCP server.

For Home Assistant add-on, HACS, and helper/config inspection workflows, the upstream repository also documents tools such as `ha_get_addon`, `ha_hacs_repository_info`, `ha_get_zone`, `ha_get_blueprint`, and `ha_config_get_*` helpers.

### Log Access Rules

- Use `ha_get_logs(source="system")` for structured Home Assistant system logs when you need recent warnings or errors.
- Use `ha_get_logs(source="error_log")` for the raw Home Assistant error log.
- Use `ha_get_logs(source="supervisor", slug="core_...")` for add-on container logs when a specific add-on is involved.
- If the `ha_mcp_tools` component is installed and the `HAMCP_ENABLE_FILESYSTEM_TOOLS=true` flag is enabled, you can read `home-assistant.log` with `ha_read_file(path="home-assistant.log", tail_lines=1000)`.
- `ha_list_files` does not browse a generic logs folder. It only lists the allowed config subdirectories (`www/`, `themes/`, `custom_templates/`).
- File access tools only work when both the `ha_mcp_tools` component and the required feature flags are present.
- For this repo, the first log checks should usually be `ha_get_logs(source="system", search="Savant")` and `ha_get_logs(source="error_log", search="Savant")`; if the component is installed, follow up with `ha_read_file(path="home-assistant.log", tail_lines=200)`.

## Wrapper Notes

- The wrapper is intentionally thin and should stay aligned with upstream `ha-mcp` expectations.
- Keep `HOMEASSISTANT_URL` and `HOMEASSISTANT_TOKEN` in `.local/hass.env`; do not hardcode them in tracked files.
- If the upstream server changes its startup contract, update the wrapper first, then adjust `.vscode/mcp.json` and this document.

## Development Workflow

1. Inspect live Home Assistant state or logs through MCP.
2. Trace the behavior back to the controlling code path in `custom_components/savant_energy/`.
3. Make the smallest edit that addresses the cause.
4. Validate immediately with the narrowest useful check.

## Troubleshooting

- If MCP does not start, verify `uvx` is on PATH and `.local/hass.env` exists.
- If MCP starts but returns no useful data, confirm the Home Assistant URL and token are valid.
- If file or YAML editing tools are needed through MCP, make sure the Home Assistant-side `ha_mcp_tools` component and feature flags are enabled.

## Repository Focus

The main surfaces to understand before changing code are:

- `custom_components/savant_energy/__init__.py` for setup and coordinator flow.
- `custom_components/savant_energy/snapshot_data.py` for Savant snapshot parsing.
- `custom_components/savant_energy/utils.py` for DMX, OLA, cache, and retry behavior.
- `custom_components/savant_energy/scene.py` and `custom_components/savant_energy/api.py` for scene management.
