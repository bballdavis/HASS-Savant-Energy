---
title: REST API
---

# Scene management over HTTP

These endpoints are served by Home Assistant when the scene-builder platform is enabled and initialized. They manage saved scenes; they do not expose a separate scene-execution endpoint.

## Authentication

Use Home Assistant’s HTTP authentication, for example an `Authorization: Bearer …` header with a suitable access token. Keep tokens out of source files and screenshots. The included dashboard card uses Home Assistant’s authenticated `hass.callApi` client.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/savant_energy/scenes` | List scene IDs and names |
| GET | `/api/savant_energy/scene_breakers/{scene_id}` | Read saved states merged with available breakers |
| POST | `/api/savant_energy/scenes` | Create a named scene |
| POST | `/api/savant_energy/scenes/{scene_id}` | Update name and/or relay states |
| DELETE | `/api/savant_energy/scenes/{scene_id}` | Delete a scene |

Paths and behavior are checked against `scene.py`; Home Assistant service schemas are in the [generated service reference](generated/services.md).

## List scenes

```http
GET /api/savant_energy/scenes
```

Example response (synthetic):

```json
{"scenes": [{"scene_id": "savant_evening_scene", "name": "Evening"}]}
```

Always use the ID returned by your installation. Do not construct it from the display name.

## Create, then edit relay states

Both `name` (nonempty string) and `relay_states` (object) are required:

```http
POST /api/savant_energy/scenes
Content-Type: application/json

{"name": "Evening", "relay_states": {}}
```

Example response:

```json
{"status": "ok", "scene_id": "savant_evening_scene"}
```

**Current implementation limitation:** creation initializes all discovered available breaker-like switches to **on**, ignoring the supplied state mapping. The discovery heuristic matches “breaker” in the entity ID or friendly name, so review the full membership list. To store deliberate states, update the scene after creation and read it back before activation:

```http
POST /api/savant_energy/scenes/savant_evening_scene
Content-Type: application/json

{
  "relay_states": {
    "switch.example_living_room_breaker": true,
    "switch.example_garage_breaker": false
  }
}
```

These are illustrative IDs; use real switch entity IDs from your installation. Update stores the supplied mapping rather than merging it with the previous mapping, so send the complete intended set. Creating or updating saved state does not itself execute the scene.

## Read breaker states

```http
GET /api/savant_energy/scene_breakers/savant_evening_scene
```

Example response:

```json
{
  "scene_id": "savant_evening_scene",
  "breakers": {
    "switch.example_living_room_breaker": true,
    "switch.example_garage_breaker": false
  }
}
```

The REST view merges saved states with discovered available breaker-like switches and defaults a newly discovered unsaved switch to **true**. The `get_scene_breakers` service handler instead defaults new members to **false**. Saved members absent from the current discovery list are retained in the response. Review every member rather than relying on a default.

## Rename or delete

```http
POST /api/savant_energy/scenes/savant_evening_scene
Content-Type: application/json

{"name": "Evening lights"}
```

```http
DELETE /api/savant_energy/scenes/savant_evening_scene
```

Update/delete views return an `ok` envelope after calling the service. They do not inspect the handler’s returned error dictionary, so an HTTP success alone does not prove the requested change persisted. Read the scene list/states back and inspect logs when validating changes.

## Error behavior

- Missing/invalid create fields and duplicate names return HTTP 400.
- The breaker-list view returns HTTP 404 for a missing scene.
- Unexpected view exceptions generally return HTTP 500.
- Authentication failures are handled by Home Assistant before the authenticated view runs.
- Service-handler error dictionaries and HTTP status behavior differ. Do not infer one from the other.

The project documents these existing behaviors; the documentation change does not alter runtime APIs. For normal dashboard use, see [Scenes card](../usage/scenes.md).
