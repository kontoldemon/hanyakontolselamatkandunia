param(
  [string]$BaseUrl = "https://cloudsentinel.zis3c.dev",
  [string]$Window = "24h",
  [string]$OutDir = "artifacts",
  [string]$AuthCookie = "",
  [string]$AuthBearer = "",
  [string]$ExtraHeadersJson = "",
  [string]$SshHost = "",
  [int]$SshPort = 0,
  [string]$SshUser = "",
  [string]$SshKey = "",
  [string]$ClickHouseDb = "default",
  [string]$ClickHouseTable = "cloudsentinel_events"
)

$ErrorActionPreference = "Stop"

function New-RequestHeaders {
  param(
    [string]$Cookie,
    [string]$Bearer,
    [string]$ExtraJson
  )
  $headers = @{}
  if ($Cookie) {
    $headers["Cookie"] = $Cookie
  }
  if ($Bearer) {
    $headers["Authorization"] = "Bearer $Bearer"
  }
  if ($ExtraJson) {
    try {
      $extra = ConvertFrom-Json -InputObject $ExtraJson
      if ($extra -and $extra.PSObject -and $extra.PSObject.Properties) {
        foreach ($prop in $extra.PSObject.Properties) {
          if ($null -ne $prop.Value -and "$($prop.Value)".Trim().Length -gt 0) {
            $headers[$prop.Name] = [string]$prop.Value
          }
        }
      }
    } catch {
      Write-Warning "invalid ExtraHeadersJson provided, ignoring"
    }
  }
  return $headers
}

function Invoke-JsonGet {
  param(
    [string]$Url,
    [hashtable]$Headers
  )
  try {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
      $tmpFile = Join-Path $env:TEMP ("truth-audit-" + [guid]::NewGuid().ToString("N") + ".json")
      $args = @("-sS", "-L", "-o", $tmpFile, "-w", "%{http_code}")
      foreach ($key in $Headers.Keys) {
        $args += @("-H", "$key`: $($Headers[$key])")
      }
      $args += $Url
      $statusText = & curl.exe @args
      $statusCode = 0
      if ($statusText) {
        try { $statusCode = [int]$statusText } catch { $statusCode = 0 }
      }
      $content = ""
      if (Test-Path $tmpFile) {
        $content = Get-Content -Path $tmpFile -Raw -ErrorAction SilentlyContinue
        Remove-Item -Path $tmpFile -Force -ErrorAction SilentlyContinue
      }
      $json = $null
      if ($content) {
        try { $json = $content | ConvertFrom-Json } catch {}
      }
      return [PSCustomObject]@{
        ok = ($statusCode -ge 200 -and $statusCode -lt 300)
        status = $statusCode
        json = $json
        error = ""
        url = $Url
      }
    }

    $resp = if ($Headers.Count -gt 0) {
      Invoke-WebRequest -Uri $Url -Method GET -UseBasicParsing -Headers $Headers
    } else {
      Invoke-WebRequest -Uri $Url -Method GET -UseBasicParsing
    }
    $json = $null
    try { $json = $resp.Content | ConvertFrom-Json } catch {}
    return [PSCustomObject]@{
      ok = $true
      status = [int]$resp.StatusCode
      json = $json
      error = ""
      url = $Url
    }
  } catch {
    $status = 0
    $errText = $_.Exception.Message
    try {
      if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $status = [int]$_.Exception.Response.StatusCode
      }
    } catch {}
    return [PSCustomObject]@{
      ok = $false
      status = $status
      json = $null
      error = $errText
      url = $Url
    }
  }
}

function Get-Value {
  param(
    [object]$Object,
    [string]$Key,
    [object]$Default = $null
  )
  if ($null -eq $Object) { return $Default }
  if ($Object -is [hashtable]) {
    if ($Object.ContainsKey($Key)) { return $Object[$Key] }
    return $Default
  }
  if ($Object.PSObject -and $Object.PSObject.Properties[$Key]) {
    return $Object.PSObject.Properties[$Key].Value
  }
  return $Default
}

function To-Int {
  param([object]$Value, [int]$Fallback = 0)
  try {
    $parsed = [int]$Value
    return $parsed
  } catch {
    return $Fallback
  }
}

function To-Bool {
  param([object]$Value, [bool]$Fallback = $false)
  if ($null -eq $Value) { return $Fallback }
  try {
    return [bool]$Value
  } catch {
    return $Fallback
  }
}

function Add-Check {
  param(
    [System.Collections.Generic.List[object]]$Rows,
    [string]$Phase,
    [string]$Name,
    [bool]$Pass,
    [string]$Expected,
    [string]$Observed
  )
  $Rows.Add([PSCustomObject]@{
    phase = $Phase
    check = $Name
    pass = $Pass
    expected = $Expected
    observed = $Observed
  }) | Out-Null
}

function Parse-ChTuple {
  param([string]$Line)
  $parts = $Line.Trim().Split("`t")
  if ($parts.Count -lt 8) {
    return $null
  }
  return [PSCustomObject]@{
    total_connections = [int]$parts[0]
    total_auth_failures = [int]$parts[1]
    total_commands = [int]$parts[2]
    total_blocks = [int]$parts[3]
    blocked_ips_current = [int]$parts[4]
    active_sessions = [int]$parts[5]
    mttb_ms = [double]$parts[6]
    total_events = [int]$parts[7]
  }
}

$rows = New-Object 'System.Collections.Generic.List[object]'
$ts = (Get-Date).ToString("yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$headers = New-RequestHeaders -Cookie $AuthCookie -Bearer $AuthBearer -ExtraJson $ExtraHeadersJson

$summaryRes = Invoke-JsonGet -Url "$BaseUrl/api/cloudsentinel/summary" -Headers $headers
$eventsRes = Invoke-JsonGet -Url "$BaseUrl/api/cloudsentinel/events" -Headers $headers
$opsRes = Invoke-JsonGet -Url "$BaseUrl/api/cloudsentinel/operations" -Headers $headers
$analyticsRes = Invoke-JsonGet -Url "$BaseUrl/api/cloudsentinel/analytics?window=$Window" -Headers $headers

$summary = $summaryRes.json
$events = $eventsRes.json
$ops = $opsRes.json
$analytics = $analyticsRes.json

$authBlocked = @($summaryRes, $eventsRes, $opsRes, $analyticsRes | Where-Object { $_.status -eq 401 }).Count -gt 0

Add-Check $rows "Phase 0 Access" "dashboard API authentication" `
  (-not $authBlocked) `
  "all endpoints reachable (not 401)" `
  ("summary={0} events={1} operations={2} analytics={3}" -f $summaryRes.status, $eventsRes.status, $opsRes.status, $analyticsRes.status)

if ($authBlocked) {
  Add-Check $rows "Phase 0 Access" "auth material provided" `
    (($headers.Count -gt 0)) `
    "cookie/bearer/extra headers passed" `
    ("headers={0}" -f ($headers.Keys -join ","))
}

# Phase 1: API truth audit
Add-Check $rows "Phase 1 API" "summary has source contract" `
  ($summaryRes.ok -and $null -ne (Get-Value $summary "source") -and $null -ne (Get-Value $summary "authoritative") -and $null -ne (Get-Value $summary "sourceBreakdown")) `
  "source+authoritative+sourceBreakdown present" `
  ("status={0} source={1} authoritative={2}" -f $summaryRes.status, (Get-Value $summary "source"), (Get-Value $summary "authoritative"))

Add-Check $rows "Phase 1 API" "events has source contract" `
  ($eventsRes.ok -and $null -ne (Get-Value $events "source") -and $null -ne (Get-Value $events "authoritative") -and $null -ne (Get-Value $events "sourceBreakdown")) `
  "source+authoritative+sourceBreakdown present" `
  ("status={0} source={1} authoritative={2}" -f $eventsRes.status, (Get-Value $events "source"), (Get-Value $events "authoritative"))

Add-Check $rows "Phase 1 API" "operations has source contract" `
  ($opsRes.ok -and $null -ne (Get-Value $ops "source") -and $null -ne (Get-Value $ops "authoritative") -and $null -ne (Get-Value $ops "sourceBreakdown")) `
  "source+authoritative+sourceBreakdown present" `
  ("status={0} source={1} authoritative={2}" -f $opsRes.status, (Get-Value $ops "source"), (Get-Value $ops "authoritative"))

Add-Check $rows "Phase 1 API" "analytics has source contract" `
  ($analyticsRes.ok -and $null -ne (Get-Value $analytics "source") -and $null -ne (Get-Value $analytics "authoritative") -and $null -ne (Get-Value $analytics "sourceBreakdown")) `
  "source+authoritative+sourceBreakdown present" `
  ("status={0} source={1} authoritative={2}" -f $analyticsRes.status, (Get-Value $analytics "source"), (Get-Value $analytics "authoritative"))

$summaryMetrics = Get-Value $summary "metrics" @{}
$totalConnections = To-Int (Get-Value $summaryMetrics "totalConnections" 0)
$totalBlocks = To-Int (Get-Value $summaryMetrics "totalBlocks" 0)

Add-Check $rows "Phase 1 API" "summary block rate bounds" `
  (($totalConnections -le 0) -or ($totalBlocks -le $totalConnections) -or (([double](Get-Value $summaryMetrics "blockRate" 0)) -le 100.0)) `
  "blockRate bounded or blocks not exceeding connections" `
  ("blocks={0} connections={1} blockRate={2}" -f $totalBlocks, $totalConnections, (Get-Value $summaryMetrics "blockRate" 0))

$summaryBlockRate = [double](Get-Value $summaryMetrics "blockRate" 0)
$summaryAvgRisk = [double](Get-Value $summaryMetrics "avgRisk" 0)
Add-Check $rows "Phase 1 API" "summary blockRate field in 0..100" `
  ($summaryBlockRate -ge 0 -and $summaryBlockRate -le 100) `
  "0 <= blockRate <= 100" `
  ("blockRate={0}" -f $summaryBlockRate)

Add-Check $rows "Phase 1 API" "summary avgRisk field in 0..100" `
  ($summaryAvgRisk -ge 0 -and $summaryAvgRisk -le 100) `
  "0 <= avgRisk <= 100" `
  ("avgRisk={0}" -f $summaryAvgRisk)

# Phase 2: War Room truth audit
Add-Check $rows "Phase 2 WarRoom" "summary source clickhouse" `
  ((Get-Value $summary "source") -eq "clickhouse") `
  "clickhouse" `
  [string](Get-Value $summary "source")

Add-Check $rows "Phase 2 WarRoom" "summary authoritative true" `
  (To-Bool (Get-Value $summary "authoritative")) `
  "true" `
  [string](Get-Value $summary "authoritative")

# Phase 3: Sessions and replay truth audit
$sensorObj = Get-Value $ops "sensor" $null
$sensorSessionsObj = if ($sensorObj) { Get-Value $sensorObj "sessions" $null } else { $null }
$sessionsData = if ($sensorSessionsObj) { Get-Value $sensorSessionsObj "data" $null } else { $null }
$sessions = @()
if ($sessionsData -and (Get-Value $sessionsData "sessions" $null)) { $sessions = @((Get-Value $sessionsData "sessions")) }
$memorySessions = @($sessions | Where-Object { $_.source -eq "memory" })
Add-Check $rows "Phase 3 Sessions" "no memory sessions in strict mode" `
  ($memorySessions.Count -eq 0) `
  "0 memory sessions" `
  ("memory sessions={0}" -f $memorySessions.Count)

$replayIpMismatch = 0
foreach ($s in $sessions) {
  if (-not $s.replay) { continue }
  foreach ($r in $s.replay) {
    if (-not $r.text) { continue }
    if ($r.text -match "^cloudsentinel\.") {
      $replayIpMismatch += 1
      break
    }
  }
}
Add-Check $rows "Phase 3 Sessions" "replay noise filtered" `
  ($replayIpMismatch -eq 0) `
  "0 replay entries with cloudsentinel.* noise" `
  ("noise sessions={0}" -f $replayIpMismatch)

# Phase 4: Intelligence KPI and timeline truth audit
Add-Check $rows "Phase 4 Intel" "analytics source clickhouse" `
  ((Get-Value $analytics "source") -eq "clickhouse") `
  "clickhouse" `
  [string](Get-Value $analytics "source")

$seriesCount = 0
if ((Get-Value $analytics "series" $null)) { $seriesCount = @((Get-Value $analytics "series")).Count }
Add-Check $rows "Phase 4 Intel" "analytics series exists" `
  ($null -ne (Get-Value $analytics "series" $null)) `
  "series array present" `
  ("series count={0}" -f $seriesCount)

# Phase 5: Settings and AI non-authoritative path audit
$opsSrc = Get-Value $ops "sourceBreakdown" $null
$opsOk = $opsSrc -and $opsSrc.sessions -and $opsSrc.attackGraph -and $opsSrc.distribution
$opsKeys = ""
if ($opsSrc -and $opsSrc.PSObject -and $opsSrc.PSObject.Properties) {
  $opsKeys = ($opsSrc.PSObject.Properties.Name -join ",")
}
Add-Check $rows "Phase 5 Settings+AI" "operations source breakdown contains telemetry keys" `
  ([bool]$opsOk) `
  "sessions+attackGraph+distribution present" `
  ("keys={0}" -f $opsKeys)

$llmSrc = if ($opsSrc) { [string]$opsSrc.llm } else { "" }
Add-Check $rows "Phase 5 Settings+AI" "llm marked non-clickhouse" `
  ($llmSrc -ne "clickhouse") `
  "llm source != clickhouse" `
  ("llm source={0}" -f $llmSrc)

# Optional direct ClickHouse compare (strict numerical comparison on summary core fields)
$chCompareRan = $false
if ($SshHost -and $SshPort -gt 0 -and $SshUser -and $SshKey) {
  $query = @"
SELECT
  countIf(eventid = 'cloudsentinel.session.connect'),
  countIf(eventid = 'cloudsentinel.login.failed'),
  countIf(eventid = 'cloudsentinel.command.input'),
  countIf(positionCaseInsensitive(cloudsentinel_soar_action, 'block') > 0),
  uniqExactIf(src_ip, positionCaseInsensitive(cloudsentinel_soar_action, 'block') > 0),
  uniqExactIf(src_ip, timestamp >= now() - INTERVAL 3 MINUTE),
  avgIf(mttb_ms, mttb_ms > 0 AND positionCaseInsensitive(cloudsentinel_soar_action, 'block') > 0),
  count()
FROM $ClickHouseDb.$ClickHouseTable
WHERE timestamp >= now() - INTERVAL 24 HOUR
  AND src_ip != ''
  AND src_ip != '0.0.0.0'
FORMAT TabSeparated
"@

  $sshArgs = @(
    "-i", $SshKey,
    "-p", "$SshPort",
    "$SshUser@$SshHost",
    "clickhouse-client --query `"$query`""
  )
  $raw = & ssh @sshArgs 2>$null
  if ($LASTEXITCODE -eq 0 -and $raw) {
    $tuple = Parse-ChTuple -Line ($raw | Select-Object -First 1)
    if ($tuple -ne $null) {
      $chCompareRan = $true
      Add-Check $rows "Phase 1 API" "summary total_connections equals ClickHouse" `
        (To-Int (Get-Value $summaryMetrics "totalConnections" 0) -eq [int]$tuple.total_connections) `
        [string]$tuple.total_connections `
        [string](Get-Value $summaryMetrics "totalConnections" 0)

      Add-Check $rows "Phase 1 API" "summary total_auth_failures equals ClickHouse" `
        (To-Int (Get-Value $summaryMetrics "totalAuthFailures" 0) -eq [int]$tuple.total_auth_failures) `
        [string]$tuple.total_auth_failures `
        [string](Get-Value $summaryMetrics "totalAuthFailures" 0)

      Add-Check $rows "Phase 1 API" "summary total_commands equals ClickHouse" `
        (To-Int (Get-Value $summaryMetrics "totalCommands" 0) -eq [int]$tuple.total_commands) `
        [string]$tuple.total_commands `
        [string](Get-Value $summaryMetrics "totalCommands" 0)
    }
  }
}

$passCount = @($rows | Where-Object { $_.pass }).Count
$failCount = $rows.Count - $passCount

$report = [PSCustomObject]@{
  generated_at = (Get-Date).ToString("o")
  base_url = $BaseUrl
  window = $Window
  totals = [PSCustomObject]@{
    checks = $rows.Count
    passed = $passCount
    failed = $failCount
    clickhouse_compare_ran = $chCompareRan
  }
  checks = $rows
  snapshots = [PSCustomObject]@{
    summary = [PSCustomObject]@{ status = $summaryRes.status; ok = $summaryRes.ok; payload = $summary }
    events = [PSCustomObject]@{ status = $eventsRes.status; ok = $eventsRes.ok; payload = $events }
    analytics = [PSCustomObject]@{ status = $analyticsRes.status; ok = $analyticsRes.ok; payload = $analytics }
    operations = [PSCustomObject]@{ status = $opsRes.status; ok = $opsRes.ok; payload = $ops }
  }
}

$outFile = Join-Path $OutDir ("clickhouse-truth-audit-" + $ts + ".json")
$report | ConvertTo-Json -Depth 10 | Out-File -FilePath $outFile -Encoding UTF8

Write-Host ""
Write-Host "CloudSentinel ClickHouse Truth Audit"
Write-Host "Base URL: $BaseUrl"
Write-Host "Output  : $outFile"
Write-Host ""
$rows | Format-Table phase, check, pass, expected, observed -AutoSize
Write-Host ""
Write-Host ("PASS={0} FAIL={1}" -f $passCount, $failCount)
if ($failCount -gt 0) {
  exit 1
}
