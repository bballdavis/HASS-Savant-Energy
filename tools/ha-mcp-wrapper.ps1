param(
    [string]$EnvFile = ".local/hass.env"
)

$ErrorActionPreference = "Stop"

function Import-EnvFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "Environment file not found at '$Path'. Copy .local/hass.env.example to .local/hass.env and fill in your Home Assistant values."
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) {
            return
        }

        $parts = $line.Split('=', 2)
        if ($parts.Count -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
        }
    }
}

Import-EnvFile -Path $EnvFile

if (-not $env:HOMEASSISTANT_URL) {
    if ($env:HASS_BASE_URL) {
        $env:HOMEASSISTANT_URL = $env:HASS_BASE_URL
    }
    else {
        throw "HOMEASSISTANT_URL is missing from $EnvFile"
    }
}

if (-not $env:HOMEASSISTANT_TOKEN) {
    if ($env:HASS_TOKEN) {
        $env:HOMEASSISTANT_TOKEN = $env:HASS_TOKEN
    }
    else {
        throw "HOMEASSISTANT_TOKEN is missing from $EnvFile"
    }
}

$env:HOMEASSISTANT_URL = $env:HOMEASSISTANT_URL.TrimEnd('/')

if (-not $env:FASTMCP_SHOW_SERVER_BANNER) {
    $env:FASTMCP_SHOW_SERVER_BANNER = "false"
}

$uvx = Get-Command uvx -ErrorAction SilentlyContinue
if (-not $uvx) {
    throw "uvx was not found on PATH. Install uv from https://docs.astral.sh/uv/getting-started/installation/ and restart VS Code."
}

& $uvx.Source --python 3.13 --refresh ha-mcp@latest
exit $LASTEXITCODE