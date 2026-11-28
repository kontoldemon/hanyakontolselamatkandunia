param(
    [ValidateSet("status", "start", "stop")]
    [string]$Action = "status",
    [ValidateSet("both", "sensor", "clickhouse")]
    [string]$Target = "both"
)

$ErrorActionPreference = "Stop"
$resourceGroup = "cloudsentinel-rg"
$sensorName = "cloudsentinel-sensor"
$clickHouseName = "cloudsentinel-clickhouse"
$fqdn = "cloudsentinel-4nxdgq72ncekc.eastasia.cloudapp.azure.com"

$az = (Get-Command az -ErrorAction SilentlyContinue).Source
if (-not $az) {
    $candidate = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
    if (Test-Path $candidate) {
        $az = $candidate
    } else {
        throw "Azure CLI not found. Install it or add az to PATH."
    }
}

function Get-VmNames {
    switch ($Target) {
        "sensor" { return @($sensorName) }
        "clickhouse" { return @($clickHouseName) }
        default { return @($clickHouseName, $sensorName) }
    }
}

function Get-VmState([string]$name) {
    $state = & $az vm get-instance-view -g $resourceGroup -n $name `
        --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" `
        -o tsv 2>$null
    if (-not $state) { return "unknown" }
    return $state.Trim()
}

function Wait-VmState([string]$name, [string]$wanted, [int]$timeoutSeconds = 180) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $state = Get-VmState $name
        if ($state -eq $wanted) { return $true }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Test-SensorHealth {
    try {
        $code = & curl.exe -sk -o NUL -w "%{http_code}" --max-time 10 "https://$fqdn/healthz" 2>$null
        return [string]$code
    } catch {
        return "000"
    }
}

function Show-Status {
    & $az vm list -d -g $resourceGroup `
        --query "[].{Name:name,State:powerState,Size:hardwareProfile.vmSize}" -o table
    $ip = & $az network public-ip show -g $resourceGroup -n cloudsentinel-sensor-pip `
        --query "ipAddress" -o tsv 2>$null
    Write-Host "Public IP: $ip"
    Write-Host "Sensor URL: https://$fqdn"
    Write-Host "Sensor health: $(Test-SensorHealth)"
}

if ($Action -eq "status") {
    Show-Status
    exit 0
}

& $az account show --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI is not logged in. Run: az login"
}

$names = Get-VmNames
if ($Action -eq "start") {
    foreach ($name in $names) {
        Write-Host "Starting $name..."
        & $az vm start -g $resourceGroup -n $name --output none
        if ($LASTEXITCODE -ne 0) { throw "Failed to start $name" }
        if (-not (Wait-VmState $name "VM running" 180)) {
            throw "$name did not reach VM running in time"
        }
        Write-Host "$name is running."
    }
    if ($names -contains $sensorName) {
        Write-Host "Waiting for the sensor admin API..."
        $healthy = $false
        for ($i = 0; $i -lt 24; $i++) {
            $code = Test-SensorHealth
            if ($code -eq "200") { $healthy = $true; break }
            Start-Sleep -Seconds 5
        }
        if (-not $healthy) {
            Write-Warning "Sensor health is not 200 yet. Check systemctl/SSH before a demo."
        } else {
            Write-Host "Sensor health: 200"
        }
    }
} else {
    foreach ($name in $names) {
        Write-Host "Deallocating $name..."
        & $az vm deallocate -g $resourceGroup -n $name --output none
        if ($LASTEXITCODE -ne 0) { throw "Failed to deallocate $name" }
        if (-not (Wait-VmState $name "VM deallocated" 180)) {
            Write-Warning "$name did not report VM deallocated in time"
        } else {
            Write-Host "$name is deallocated."
        }
    }
    Write-Host "Compute billing stopped. Disks, static IP and network resources still bill (~`$0.05/day)."
}

Show-Status
