param(
  [string]$BaseUrl = "https://188.166.184.42.sslip.io",
  [string]$BearerToken = "",
  [string]$OutDir = "artifacts"
)

$ErrorActionPreference = "Stop"

function Invoke-JsonGet {
  param(
    [string]$Url,
    [hashtable]$Headers
  )
  try {
    $resp = Invoke-WebRequest -Uri $Url -Method GET -UseBasicParsing -Headers $Headers
    $json = $null
    try { $json = $resp.Content | ConvertFrom-Json } catch {}
    return [PSCustomObject]@{
      ok = $true
      status = [int]$resp.StatusCode
      json = $json
      error = ""
    }
  } catch {
    $status = 0
    $msg = $_.Exception.Message
    try {
      if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $status = [int]$_.Exception.Response.StatusCode
      }
    } catch {}
    return [PSCustomObject]@{
      ok = $false
      status = $status
      json = $null
      error = $msg
    }
  }
}

function Add-Check {
  param(
    [System.Collections.Generic.List[object]]$Rows,
    [string]$Name,
    [bool]$Pass,
    [string]$Expected,
    [string]$Observed
  )
  $Rows.Add([PSCustomObject]@{
    check = $Name
    pass = $Pass
    expected = $Expected
    observed = $Observed
  }) | Out-Null
}

if (-not $BearerToken) {
  throw "BearerToken required"
}

$headers = @{ Authorization = "Bearer $BearerToken" }
$rows = New-Object 'System.Collections.Generic.List[object]'

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$ts = (Get-Date).ToString("yyyyMMdd-HHmmss")

$readiness = Invoke-JsonGet -Url "$BaseUrl/readiness" -Headers $headers
$events = Invoke-JsonGet -Url "$BaseUrl/events?limit=200" -Headers $headers
$sessions = Invoke-JsonGet -Url "$BaseUrl/sessions" -Headers $headers
$dist = Invoke-JsonGet -Url "$BaseUrl/attack-distribution" -Headers $headers
$graph = Invoke-JsonGet -Url "$BaseUrl/attack-graph" -Headers $headers
$truth = Invoke-JsonGet -Url "$BaseUrl/truth-summary" -Headers $headers

Add-Check $rows "readiness auth ok" ($readiness.status -eq 200) "200" ([string]$readiness.status)
Add-Check $rows "events auth ok" ($events.status -eq 200) "200" ([string]$events.status)
Add-Check $rows "sessions auth ok" ($sessions.status -eq 200) "200" ([string]$sessions.status)
Add-Check $rows "distribution auth ok" ($dist.status -eq 200) "200" ([string]$dist.status)
Add-Check $rows "graph auth ok" ($graph.status -eq 200) "200" ([string]$graph.status)
Add-Check $rows "truth summary auth ok" ($truth.status -eq 200) "200" ([string]$truth.status)

$eventsSource = if ($events.json) { [string]$events.json.source } else { "" }
$sessionsSource = if ($sessions.json) { [string]$sessions.json.source } else { "" }
$graphSource = if ($graph.json) { [string]$graph.json.source } else { "" }
$truthSource = if ($truth.json) { [string]$truth.json.source } else { "" }
$truthAuthoritative = if ($truth.json) { [bool]$truth.json.authoritative } else { $false }

Add-Check $rows "events source clickhouse" ($eventsSource -eq "clickhouse") "clickhouse" $eventsSource
Add-Check $rows "sessions source clickhouse strict" ($sessionsSource -eq "clickhouse") "clickhouse" $sessionsSource
Add-Check $rows "graph source clickhouse strict" ($graphSource -eq "clickhouse") "clickhouse" $graphSource
Add-Check $rows "truth summary source clickhouse" ($truthSource -eq "clickhouse") "clickhouse" $truthSource
Add-Check $rows "truth summary authoritative true" $truthAuthoritative "true" ([string]$truthAuthoritative)

$memoryCount = 0
if ($sessions.json -and $sessions.json.sessions) {
  $memoryCount = @($sessions.json.sessions | Where-Object { $_.source -eq "memory" }).Count
}
Add-Check $rows "strict mode memory sessions excluded" ($memoryCount -eq 0) "0" ([string]$memoryCount)

$metrics = if ($truth.json) { $truth.json.metrics } else { $null }
$avgRisk = if ($metrics) { [double]$metrics.avg_risk } else { -1 }
$blockRate = if ($metrics) { [double]$metrics.block_rate } else { -1 }
Add-Check $rows "avg_risk bounded 0..100" ($avgRisk -ge 0 -and $avgRisk -le 100) "0..100" ([string]$avgRisk)
Add-Check $rows "block_rate bounded 0..100" ($blockRate -ge 0 -and $blockRate -le 100) "0..100" ([string]$blockRate)

$passCount = @($rows | Where-Object { $_.pass }).Count
$failCount = $rows.Count - $passCount

$report = [PSCustomObject]@{
  generated_at = (Get-Date).ToString("o")
  base_url = $BaseUrl
  totals = [PSCustomObject]@{
    checks = $rows.Count
    passed = $passCount
    failed = $failCount
  }
  checks = $rows
  snapshots = [PSCustomObject]@{
    readiness = $readiness.json
    truth = $truth.json
  }
}

$outFile = Join-Path $OutDir ("sensor-truth-audit-" + $ts + ".json")
$report | ConvertTo-Json -Depth 10 | Out-File -FilePath $outFile -Encoding UTF8

Write-Host ""
Write-Host "CloudSentinel Sensor Truth Audit"
Write-Host "Base URL: $BaseUrl"
Write-Host "Output  : $outFile"
Write-Host ""
$rows | Format-Table check, pass, expected, observed -AutoSize
Write-Host ""
Write-Host ("PASS={0} FAIL={1}" -f $passCount, $failCount)
if ($failCount -gt 0) {
  exit 1
}
