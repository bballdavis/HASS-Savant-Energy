# Savant Energy Home Assistant Integration

Welcome to the **Savant Energy** integration for Home Assistant! This project brings Savant relay and energy monitoring devices into your smart home, providing real-time power, voltage, relay control, and more, all with a beautiful, open-source touch.

For the current protocol migration and the 2.0.0 release details, see [the current API workflow](docs/current-api-workflow.md) and [the release notes](docs/release-notes-v2.0.0.md).

## Features

- **Automatic device discovery** from your Savant system
- **Power, current, and voltage sensors** for each circuit
- **Per-load cumulative energy sensors** in `kWh` sourced directly from SEM hardware counters, ready for the Home Assistant Energy dashboard
- **CT-monitored load sensors** for non-switched loads (EV chargers, solar, etc.)
- **Relay (breaker) switch control** with configurable cooldown
- **Relay binary sensors** for relay status
- **All Loads On button** to quickly turn all loads on
- **Hub-level system sensors** for total consumption, solar, battery, grid, and load group totals
- **DMX address sensors** for legacy relay control (legacy mode only)
- **Custom Lovelace card** for managing energy scenes
- **REST API** for programmatic control and monitoring of scenes
- **Scene buttons** for quick activation of predefined scenes
- **Integrated Scene Builder** within the Lovelace card
- **Mode-based setup** for Legacy (<11.2), Current (>=11.2), and Auto detection

---

## Installation (via HACS)

1. **Add the repository to HACS**
   - In Home Assistant, go to **HACS > Integrations > Custom repositories**
   - Add: `https://github.com/bballdavis/HASS-Savant-Energy`
   - Set category to **Integration**

2. **Install the integration**
   - Search for **Savant Energy** in HACS and click **Install**

3. **Restart Home Assistant**

4. **Add the integration**
   - Go to **Settings > Devices & Services > Add Integration**
   - Search for **Savant Energy** and follow the setup prompts

### Choosing your setup mode

| Mode | When to use | What you need |
|---|---|---|
| **Auto** *(recommended)* | New installs - the integration figures out which version you have | PBC IP address |
| **Legacy (<11.2)** | Older Savant firmware, snapshot + DMX workflow | PBC IP address |
| **Current (>=11.2)** | Savant firmware 11.2 or later | PBC IP, Host IP, RPM SSH password (one-time bootstrap) |

In **Auto** mode, the integration first tries the legacy feed. If it doesn't find one, it prompts for the Host IP and continues to SSH bootstrap (see the Current mode section below).

If you're on **Legacy** mode and the integration can no longer reach its data source, it will create a Home Assistant notification pointing you to the **Reconfigure** flow.

---

## Upgrading from Legacy to Current Mode

If you've been running the integration in Legacy mode and you've upgraded your Savant firmware to 11.2 or later, here's the clean migration path:

1. **Go to Settings > Devices & Services** and find your Savant Energy integration entry
2. Click the **three-dot menu > Reconfigure**
3. Change the mode to **Current** (or leave it on **Auto** and let it detect)
4. Provide your **Host IP** (the Savant host running InfluxDB, often a different IP from the PBC)
5. Enter the **RPM SSH password** so the integration can validate and manage the InfluxDB token

**What happens to your existing entities?**

The integration is designed to migrate cleanly. Device and entity history, automations, and energy dashboard data are all tied to the underlying entity unique IDs, and those are preserved across the mode switch:

- Relay-controlled circuits are matched by name through the SEM companion API, which provides the original MAC-based hardware identifiers. Your existing entities are updated in place with no orphaned duplicates.
- CT-monitored loads (EV chargers, solar inverters) that didn't exist in legacy mode will appear as new sensor entities.
- Any truly stale entities (circuits that no longer exist in the hardware inventory) are automatically cleaned up on the first load.

You should end up with the same devices you had before, plus a handful of new system-level and CT-monitored sensors. Nothing gets recreated from scratch.

---

## What Changed in Current Mode (>=11.2)

Why all of this? - Savant completely overhauled how the Panel Bridge Controller and the Smart Energy Monitor communicate starting in firmware 11.2. The old integration worked by connecting directly to a TCP feed on the PBC and scraping a snapshot of the relay states. It was a bit of a hack, but it worked.

In 11.2, Savant moved to a proper time-series architecture. The energy data now flows directly into an **InfluxDB 2** instance running on the Savant host. This is actually a huge upgrade - instead of a snapshot, we get rich historical data, real hardware energy counters (not integrated estimates), and access to a whole bunch of channels that the old TCP feed never exposed, like solar production, battery state, grid availability, and load group totals.

The relay control side got cleaned up too. Instead of routing commands through the DMX/OLA layer, we talk directly to the SEM over a simple TCP protocol on port 2000. It's more reliable and noticeably faster.

**The one setup requirement: SSH access to the Savant host.**

If Current-mode setup fails, use the [SSH troubleshooting guide](docs/troubleshooting-ssh.md) to capture focused Home Assistant logs and check the host connection.

InfluxDB uses a token-based auth model, but normal setup retrieves the read token over SSH rather than asking you to copy it. During setup, enter the `RPM` user's password. The integration reads the token from the host, validates a candidate against real Savant circuit data, installs a refresh key, and then creates the entry. Your password is used only for that bootstrap operation and is never stored. The generated SSH private key and validated InfluxDB token are stored in Home Assistant's encrypted config storage.

That SSH key is not just for first setup. If InfluxDB later rejects the token with an auth failure, the integration uses the stored key to fetch a fresh token automatically, so normal token rotation or host restarts do not require re-entering the SSH password.

**To find or set your SSH password:**
- Try the default: **`RPM`**
- If that doesn't work, and you have access to the **Savant Application Manager**, open the **System Monitor** app, right-click your host, and choose **Set Password** to assign a new one

If SSH setup needs diagnosis, the host may store its token at either `/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken` or `/data/home/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken`. Do not copy or share token contents; the integration checks both locations safely. The adjacent `.influxsetup` and `.influxtoken` metadata files help it resolve the organization and bucket.

Existing token-only entries remain supported at runtime. Reconfigure moves them to the SSH bootstrap flow without changing the saved token, authentication provenance, or key until validation and key installation both succeed.

---

## How to Use

Once installed and configured, the integration automatically creates entities for each circuit it discovers.

### Entity Breakdown

**Per-circuit (all circuits):**
- **Power Sensor** (`sensor.<device>_power`) - real-time power in Watts
- **Current Sensor** (`sensor.<device>_current`) - Amperes
- **Voltage Sensor** (`sensor.<device>_voltage`) - Volts
- **Energy Sensor** (`sensor.<device>_energy`) - cumulative kWh from the SEM hardware counter; add this to the Home Assistant Energy dashboard under individual devices

**Relay-controlled circuits only:**
- **Breaker Switch** (`switch.<device>_breaker`) - turn the relay on/off; includes a configurable cooldown (default: 15 s) to protect hardware
- **Relay Status Binary Sensor** (`binary_sensor.<device>_relay_status`) - whether the relay is commanded on or off
- **DMX Address Sensor** (`sensor.<device>_dmx_address`) - legacy mode only

**Hub-level system sensors:**
- Total Consumption, Grid Feed, Net Power
- Solar Power, Solar Producing
- Battery Power, State of Charge, Time Remaining, Operating Mode
- Grid Available
- Load group totals: HVAC, Lighting, Appliances, Room, Outlet, Garage, Refrigerator, Microwave, Network

**Control buttons:**
- **All Loads On** - turns every relay on in one shot
- **Scene Buttons** - one button per saved scene
- **DMX API Command Log / DMX API Statistics** - diagnostic buttons (legacy mode)

---

## Savant Energy Scenes Card

The integration ships a custom Lovelace card for building and running scenes.

**To add it to a dashboard:**
1. Edit any dashboard > Add Card > Manual (at the bottom)
2. Enter:
```yaml
type: custom:savant-energy-scenes-card
```

**Card features:**
- Create, edit, and delete scenes
- Set per-relay on/off state for each scene
- One-press scene execution

**If the card doesn't load** ("Custom element doesn't exist"):
1. Confirm the integration is set up and HA has restarted
2. Check **Settings > Dashboards > Resources** for `/local/savant-energy-scenes-card.js`
3. If missing, add it manually as type `module`
4. Clear browser cache and reload

---

## REST API

The integration exposes a REST API for scene management.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/savant_energy/scenes` | List all scenes |
| `GET` | `/api/savant_energy/scene_breakers/{scene_id}` | Get relay states for a scene |
| `POST` | `/api/savant_energy/scenes` | Create a new scene |
| `POST` | `/api/savant_energy/scenes/{scene_id}` | Update a scene |
| `DELETE` | `/api/savant_energy/scenes/{scene_id}` | Delete a scene |

**Create a scene:**
```json
POST /api/savant_energy/scenes
{ "name": "Evening Wind Down" }
```

**Update relay states:**
```json
POST /api/savant_energy/scenes/savant_evening_wind_down_scene
{
  "relay_states": {
    "switch.living_room_breaker": true,
    "switch.patio_light_breaker": false
  }
}
```

See `INTEGRATION_API.md` for full documentation.

---

## Configuration Options

| Option | Default | Description |
|---|---|---|
| Mode | Auto | Auto, Legacy, or Current |
| PBC IP Address | (required) | IP of the Panel Bridge Controller |
| Host IP Address | (required for Current) | IP of the Savant host running InfluxDB |
| SSH Bootstrap | (required for Current) | One-time RPM password; retrieves and manages the validated InfluxDB read token |
| Scan Interval | 5 s | How often to poll for new data |
| Breaker Cooldown | 15 s | Minimum seconds between relay toggles |
| Pending Confirm Multiplier | 2x | Coordinator cycles to wait for relay confirmation |
| DMX Testing Mode | Off | Log DMX commands without sending (legacy, diagnostic) |

---

## InfluxDB Discovery Tool

A standalone discovery tool is included for exploring InfluxDB data on your Savant host, useful for understanding available measurements and diagnosing setup.

**Setup:**
```bash
pip install -r tools/requirements-dev.txt
cp .savant-local.env.example .savant-local.env
# Edit .savant-local.env with your host IP and credentials
```

**Full discovery run:**
```bash
python3 tools/savant_influx_probe.py discover \
  --ssh-host 192.168.1.14 \
  --ssh-user RPM \
  --cache-token
```

This prompts for your SSH password, retrieves and caches the InfluxDB token, then generates a full discovery report in `savant_influx_discovery/YYYYMMDD-HHMMSS/` covering measurements, fields, tags, and sample data.

---

## File Structure

| File | Purpose |
|---|---|
| `__init__.py` | Integration setup and coordinator |
| `influx_client.py` | InfluxDB queries and circuit data parsing |
| `relay_control.py` | Direct SEM TCP relay controller |
| `sensor.py`, `power_device_sensor.py` | Circuit and system sensors |
| `switch.py` | Breaker switch entities |
| `binary_sensor.py` | Relay status sensors |
| `button.py` | Control and diagnostic buttons, scene buttons |
| `dmx_address_sensor.py` | DMX address sensors (legacy) |
| `scene.py` | Scene storage, management, and execution |
| `api.py` | HA service handlers and REST views |
| `utils.py` | Shared utility functions |
| `models.py` | Device model helpers |
| `const.py` | All constants and defaults |
| `savant-energy-scenes-card.js` | Lovelace scene builder card |

---

## Contributing

### Savant host token locations and recovery

Current SavantOS releases may store the Influx read token under either layout:

```text
/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken
/data/home/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken
```

Adjacent `.influxsetup` and `.influxtoken` files contain useful organization and bucket metadata. When diagnosing over SSH, inspect only paths and file sizes, for example `find /data -path '*/InfluxDB2/.influxReadtoken' -print` and `wc -c <path>`; never print token contents. `influxd` is the InfluxDB daemon, not the `influx` command-line client, and it may not be installed. The integration validates candidate tokens with a real query before saving one and retries after token rotation.

SSH refresh appends the integration key to `authorized_keys`, verifies key login and token access, and rolls back only its exact appended byte suffix on failure. If the file changed concurrently, it leaves that content untouched. A historical backfill is identity inventory only: live availability and controls use fresh measurements, and partial inventory never removes existing entities.

We love contributions! Please:
- Open issues for bugs or feature requests
- Submit pull requests with clear descriptions
- Follow the code style

This project uses AI coding agents during development, but all code changes are reviewed and tested before release.

## License

This project is licensed under the GNU GPL v3. See `LICENSE` for details.

---

**Enjoy your smarter, more open Savant system!**

For help, visit the [GitHub repo](https://github.com/bballdavis/HASS-Savant-Energy) or open an issue.
