param(
    [string[]]$EntityId = @(),
    [switch]$IntegrationDiagnostics,
    [switch]$IncludeAttributes,
    [switch]$Logs
)

$ErrorActionPreference = 'Stop'

$mcpRepo = Resolve-Path (Join-Path $PSScriptRoot '..\..\hass-mcp')
$envPath = Join-Path $mcpRepo '.env'
$urlLine = Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^HA_MCP_URL=' } | Select-Object -First 1
if (-not $urlLine) { throw 'HA_MCP_URL was not found in the hass-mcp .env file.' }
$mcpUrl = $urlLine.Split('=', 2)[1].Trim()

function Invoke-HaMcpTool {
    param([int]$Id, [string]$Name, [hashtable]$Arguments)
    $payload = [ordered]@{
        jsonrpc = '2.0'
        id = $Id
        method = 'tools/call'
        params = @{ name = $Name; arguments = $Arguments }
    } | ConvertTo-Json -Depth 30 -Compress
    $requestPath = Join-Path $env:TEMP "savant-ha-mcp-$Id.json"
    try {
        Set-Content -LiteralPath $requestPath -Value $payload -NoNewline
        $raw = & curl.exe -sS -X POST $mcpUrl -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' --data-binary "@$requestPath"
        if ($LASTEXITCODE -ne 0) { throw "HA MCP request failed for $Name." }
        $dataLine = $raw -split "`r?`n" | Where-Object { $_ -like 'data: *' } | Select-Object -First 1
        if (-not $dataLine) { throw "HA MCP returned no SSE data for $Name." }
        $rpc = ($dataLine -replace '^data:\s*', '') | ConvertFrom-Json
        if ($rpc.error) { throw ($rpc.error | ConvertTo-Json -Depth 10 -Compress) }
        $text = $rpc.result.content | Where-Object type -eq 'text' | Select-Object -First 1 -ExpandProperty text
        if (-not $text) { return $null }
        return $text | ConvertFrom-Json
    }
    finally {
        Remove-Item -LiteralPath $requestPath -ErrorAction SilentlyContinue
    }
}

$requestId = 1
foreach ($id in $EntityId) {
    $result = Invoke-HaMcpTool -Id $requestId -Name 'ha_get_state' -Arguments @{ entity_id = $id }
    $requestId++
    if ($result.data) { $result = $result.data }
    $state = [ordered]@{
        entity_id = $id
        state = $result.state
        last_changed = $result.last_changed
        last_updated = $result.last_updated
        last_reported = $result.last_reported
        installed_version = $result.attributes.installed_version
        latest_version = $result.attributes.latest_version
    }
    if ($IncludeAttributes) { $state.attributes = $result.attributes }
    [pscustomobject]$state
}

if ($IntegrationDiagnostics) {
    Invoke-HaMcpTool -Id $requestId -Name 'ha_get_integration' -Arguments @{
        entry_id = '01K9FXXK0N0VF08TSYF179V9MZ'
        include_diagnostics = $true
        diagnostics_truncate_at_bytes = 50000
    } | ConvertTo-Json -Depth 30
}

if ($Logs) {
    Invoke-HaMcpTool -Id ($requestId + 1) -Name 'ha_get_logs' -Arguments @{
        source = 'error_log'
        search = 'savant'
        structured = $true
        hours_back = 24
    } | ConvertTo-Json -Depth 30
}
