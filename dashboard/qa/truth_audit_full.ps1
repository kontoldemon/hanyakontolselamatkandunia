param(
  [string]$DashboardBaseUrl = "https://cloudsentinel.zis3c.dev",
  [string]$SensorBaseUrl = "https://188.166.184.42.sslip.io",
  [string]$OutDir = "artifacts",
  [string]$AuthCookie = "",
  [string]$AuthBearer = "",
  [string]$SshHost = "188.166.184.42",
  [int]$SshPort = 22222,
  [string]$SshUser = "root",
  [string]$AdminTokenPath = "/root/cloudsentinel-admin-token",
  [string]$SensorBearerToken = ""
)

$ErrorActionPreference = "Stop"

function Read-SensorTokenFromSsh {
  param(
    [string]$HostName,
    [int]$Port,
    [string]$User,
    [string]$TokenPath
  )
  try {
    $raw = & ssh "-p" "$Port" "$User@$HostName" "cat $TokenPath" 2>$null
    if ($LASTEXITCODE -ne 0) {
      return ""
    }
    return [string]($raw | Out-String).Trim()
  } catch {
    return ""
  }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$qaDir = Join-Path $root "qa"
$dashboardScript = Join-Path $qaDir "truth_audit.ps1"
$sensorScript = Join-Path $qaDir "truth_audit_sensor.ps1"

$summary = [ordered]@{
  generated_at = (Get-Date).ToString("o")
  dashboard_attempted = $false
  dashboard_passed = $false
  sensor_attempted = $false
  sensor_passed = $false
  notes = @()
}

if ($AuthCookie -or $AuthBearer) {
  $summary.dashboard_attempted = $true
  try {
    & powershell -ExecutionPolicy Bypass -File $dashboardScript `
      -BaseUrl $DashboardBaseUrl `
      -OutDir $OutDir `
      -AuthCookie $AuthCookie `
      -AuthBearer $AuthBearer
    if ($LASTEXITCODE -eq 0) {
      $summary.dashboard_passed = $true
    } else {
      $summary.notes += "dashboard audit returned non-zero exit code: $LASTEXITCODE"
    }
  } catch {
    $summary.notes += "dashboard audit exception: $($_.Exception.Message)"
  }
} else {
  $summary.notes += "dashboard auth not provided, dashboard audit skipped"
}

$resolvedSensorToken = $SensorBearerToken
if (-not $resolvedSensorToken) {
  $resolvedSensorToken = Read-SensorTokenFromSsh -HostName $SshHost -Port $SshPort -User $SshUser -TokenPath $AdminTokenPath
}

if ($resolvedSensorToken) {
  $summary.sensor_attempted = $true
  try {
    & powershell -ExecutionPolicy Bypass -File $sensorScript `
      -BaseUrl $SensorBaseUrl `
      -OutDir $OutDir `
      -BearerToken $resolvedSensorToken
    if ($LASTEXITCODE -eq 0) {
      $summary.sensor_passed = $true
    } else {
      $summary.notes += "sensor audit returned non-zero exit code: $LASTEXITCODE"
    }
  } catch {
    $summary.notes += "sensor audit exception: $($_.Exception.Message)"
  }
} else {
  $summary.notes += "sensor token unavailable via parameter or ssh"
}

$ok = $summary.sensor_passed -and (($summary.dashboard_attempted -eq $false) -or $summary.dashboard_passed)
$summary.ok = $ok

$outFile = Join-Path $OutDir ("truth-audit-full-" + (Get-Date).ToString("yyyyMMdd-HHmmss") + ".json")
$summary | ConvertTo-Json -Depth 6 | Out-File -FilePath $outFile -Encoding UTF8

Write-Host ""
Write-Host "CloudSentinel Full Truth QA"
Write-Host "Output: $outFile"
Write-Host ("dashboard: attempted={0} passed={1}" -f $summary.dashboard_attempted, $summary.dashboard_passed)
Write-Host ("sensor   : attempted={0} passed={1}" -f $summary.sensor_attempted, $summary.sensor_passed)
if ($summary.notes.Count -gt 0) {
  Write-Host "notes:"
  foreach ($n in $summary.notes) {
    Write-Host ("- " + $n)
  }
}

if (-not $ok) {
  exit 1
}
