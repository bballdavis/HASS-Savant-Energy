# Savant Energy Home Assistant Integration

Welcome to the **Savant Energy** integration for Home Assistant! This project brings Savant relay and energy monitoring devices into your smart home, providing real-time power, voltage, relay control, and more—all with a beautiful, open-source touch.

## 🚀 Features
- **Automatic device discovery** from your Savant system
- **Power and voltage sensors** for each relay
- **Per-load cumulative energy sensors** in `kWh` for use with the Home Assistant Energy dashboard
- **Relay (breaker) switch control** with configurable cooldown
- **Relay Binary sensors** for relay status
- **All Loads On Button** to quickly turn all loads on
- **DMX address sensors** for controlling individual breakers
- **Custom Lovelace card** for managing energy scenes
- **REST API** for programmatic control and monitoring of scenes (could expose more if desired)
- **Scene Buttons** for quick activation of predefined scenes
- **Integrated Scene Builder** within the Lovelace card

## 🛠️ Installation (via HACS)
1. **Add the repository to HACS**:
   - In Home Assistant, go to **HACS > Integrations > Custom repositories**.
   - Add your fork or this repo's URL: `https://github.com/bballdavis/HASS-Savant-Energy`.
   - Set category to **Integration**.
2. **Install the integration**:
   - Search for **Savant Energy** in HACS and click **Install**.
3. **Restart Home Assistant** to load the integration.
4. **Add the integration**:
   - Go to **Settings > Devices & Services > Add Integration**.
   - Search for **Savant Energy** and follow the prompts.
   - Add you Panel Controller Bridge's (PCB) IP address.
   - The port defaults should work, but you can change it if needed.

## ⚡ How to Use
Once installed and configured, the integration will automatically create entities for each Savant relay device it discovers. Here’s what you’ll see:

### Entity Breakdown
- **Power Sensor (`sensor.<device>_power`)**: Shows the real-time power usage (Watts) for each relay.
- **Energy Sensor (`sensor.<device>_energy`)**: Tracks cumulative energy usage (kWh) for each relay and can be added to Home Assistant's Energy dashboard under individual devices.
- **Voltage Sensor (`sensor.<device>_voltage`)**: Displays the current voltage (Volts) for each relay.
- **Breaker Switch (`switch.<device>_breaker`)**: Lets you turn the relay on/off. Includes a configurable cooldown (default: 30 seconds) to prevent rapid toggling and protect your hardware.
- **Relay Status Binary Sensor (`binary_sensor.<device>_relay_status`)**: Indicates if the relay is currently ON or OFF.
- **DMX Address Sensor (`sensor.<device>_dmx_address`)**: (Advanced) Shows the DMX address assigned to the relay.
- **Scene Buttons (`button.<scene_name>`)**: Activates the predefined scene.
- **Diagnostic Buttons**:
  - **All Loads On**: Instantly turns on all relays.
  - **API Command Log**: Logs a sample DMX API command for troubleshooting.
  - **API Stats**: Shows DMX API health and statistics.

## 📱 Savant Energy Scenes Card

### Using the Card
The integration includes a custom Lovelace card for managing Savant Energy scenes. To use it:

1. Edit any dashboard
2. Click "Add Card"
3. Choose "Manual" at the bottom
4. Enter the following YAML:
```yaml
type: custom:savant-energy-scenes-card
```

### Card Features
- Create, edit, and delete Savant Energy scenes
- Control which relays are active in each scene
- Simple and intuitive interface for managing scenes
- Integrated scene builder for a seamless experience

### Troubleshooting the Card
If the card doesn't load with an error like "Custom element doesn't exist: savant-energy-scenes-card":

1. Verify the integration is properly set up
2. Check that the JS file exists in `/config/www/savant-energy-scenes-card.js`
3. Verify resource registration: Settings > Dashboards > Resources
4. If needed, add the resource manually: `/local/savant-energy-scenes-card.js` with type `module`
5. Clear your browser cache and reload Home Assistant

## 🔌 REST API
This integration exposes a REST API for managing Savant Energy scenes.

**API Endpoints:**

*   **`GET /api/savant_energy/scenes`**: Retrieves a list of all Savant scenes.
    *   **Response:** A JSON object containing a list of scenes, each with `scene_id` and `name`.
*   **`GET /api/savant_energy/scene_breakers/{scene_id}`**: Returns the breaker (relay) states for a specific scene.
    *   **Path Parameter:** `scene_id` (string, required) - The ID of the scene.
    *   **Response:** A JSON object with `scene_id` and a `breakers` object, where keys are breaker entity IDs and values are boolean states (true for on, false for off).
*   **`POST /api/savant_energy/scenes`**: Creates a new Savant scene.
    *   **Request Body (JSON):**
        ```json
        {
          "name": "My New Scene"
        }
        ```
    *   **Response (Success):** A JSON object with `status: "ok"` and the new `scene_id`.
    *   **Response (Error):** A JSON object with `status: "error"`, a `message`, and an `error` type (e.g., `scene_exists`).
*   **`POST /api/savant_energy/update_scene`**: Updates an existing Savant scene.
    *   **Request Body (JSON):**
        ```json
        {
          "scene_id": "savant_my_new_scene",
          "name": "My Updated Scene Name",
          "relay_states": {
            "switch.breaker_living_room": true,
            "switch.breaker_kitchen": false
          }
        }
        ```
    *   **Response (Success):** A JSON object with `status: "ok"` and the `scene_id`.
*   **`POST /api/savant_energy/delete_scene`**: Deletes a Savant scene.
    *   **Request Body (JSON):**
        ```json
        {
          "scene_id": "savant_my_updated_scene_name"
        }
        ```
    *   **Response (Success):** A JSON object with `status: "ok"` and the `scene_id` of the deleted scene.

Refer to `INTEGRATION_API.md` for more detailed API documentation, including example requests and responses.

## 🔬 InfluxDB Discovery Tool

The Savant host stores InfluxDB 2 data locally. A discovery tool is provided to explore and understand the available measurements, fields, and tags for building an optimized integration.

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r tools/requirements-dev.txt
   ```

2. **Configure local credentials** (gitignored):
   ```bash
   cp .savant-local.env.example .savant-local.env
   # Edit .savant-local.env with your Savant host IP and SSH credentials
   ```

### Quick Start

Run a full discovery of the InfluxDB on your Savant host:

```bash
python3 tools/savant_influx_probe.py discover \
  --ssh-host 192.168.1.14 \
  --ssh-user RPM \
  --cache-token
```

The script will:
- Prompt for your SSH password
- Retrieve the InfluxDB read token from the Savant host
- Query all organizations, buckets, measurements, fields, and tags
- Sample recent data rows
- Generate a detailed discovery report in `savant_influx_discovery/YYYYMMDD-HHMMSS/`

### Available Commands

**Full discovery:**
```bash
python3 tools/savant_influx_probe.py discover \
  --influx-url http://192.168.1.14:8086 \
  --ssh-host 192.168.1.14 \
  --ssh-user RPM
```

**List organizations:**
```bash
python3 tools/savant_influx_probe.py list-orgs \
  --influx-url http://192.168.1.14:8086 \
  --token "<your_token>"
```

**List buckets:**
```bash
python3 tools/savant_influx_probe.py list-buckets \
  --influx-url http://192.168.1.14:8086 \
  --token "<your_token>" \
  --org "<org_name>"
```

### Output

Discovery generates structured reports in `savant_influx_discovery/YYYYMMDD-HHMMSS/`:
- **orgs.json**: Organization definitions
- **buckets.json**: Buckets per organization
- **measurements.json**: Available measurements
- **fields.json**: Available field keys (power, energy, voltage, current, etc.)
- **tags.json**: Available tag keys (name, uid, channel, classification, etc.)
- **tag_values.json**: Sample values for key tags
- **recent_sample_*.csv / .jsonl**: Recent data rows
- **candidate_energy_series.json**: Scored candidates for energy/power data
- **summary.md**: Human-readable summary with recommendations

### Token Caching

Use `--cache-token` to store the retrieved token locally in `.savant-influx-read.token` (gitignored). This speeds up subsequent runs:

```bash
# First run: retrieves and caches token
python3 tools/savant_influx_probe.py discover --cache-token

# Subsequent runs: uses cached token (no SSH prompt)
python3 tools/savant_influx_probe.py discover
```

## 📝 Configuration Options
- **IP Address**: The address of your Savant controller.
- **Port**: The port for energy snapshot data (default: 2000).
- **OLA Port**: The port for DMX/OLA API (default: 9090).
- **Scan Interval**: How often to poll for new data (default: 15s).
- **Breaker Cooldown**: Minimum seconds between relay toggles (default: 30s).
- **DMX Testing Mode**: Enable for advanced DMX testing (optional). This mode is a testing mode for viewing the DMX command to be sent without actually sending it (console only).

## 🧑‍💻 Contributing
We love contributions! Please:
- Open issues for bugs or feature requests
- Submit pull requests with clear descriptions
- Follow the code style and add docstrings/comments

This project uses AI coding agents during development, but all code changes are reviewed and tested before release.

## 📚 File Structure
- `__init__.py`: Integration setup and coordinator logic
- `api.py`: Handles REST API requests and responses.
- `sensor.py`, `power_device_sensor.py`: Power/voltage sensors
- `switch.py`: Relay (breaker) switch logic
- `binary_sensor.py`: Relay status sensors
- `button.py`: Diagnostic and control buttons, including scene buttons.
- `dmx_address_sensor.py`: DMX address sensors
- `scene.py`: Manages scene creation, modification, and deletion.
- `utils.py`: Utility functions (DMX, API, etc.)
- `snapshot_data.py`: Fetches energy snapshot from Savant
- `models.py`: Device model helpers
- `const.py`: Constants
- `savant-energy-scenes-card.js`: Powers the Lovelace card, including the scene builder.

## 🏷️ License
This project is licensed under the GNU GPL v3. See `LICENSE` for details.

---

**Enjoy your smarter, more open Savant system!**

For help, visit the [GitHub repo](https://github.com/bballdavis/HASS-Savant-Energy) or open an issue.
