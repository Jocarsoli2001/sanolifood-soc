[CmdletBinding()]
param(
    [string]$ManagerAddress = '10.20.0.10',
    [string]$RunId = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$results = New-Object System.Collections.Generic.List[object]

if ($RunId -and $RunId -notmatch '^SF-EVAL-SCN-[0-9]{3}-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$') {
    throw 'Invalid evaluation run identifier.'
}
if (-not $RunId) {
    $RunId = "manual-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))"
}

function Add-Result {
    param([string]$Check, [bool]$Success, [string]$Detail)
    $results.Add([PSCustomObject]@{
        Status = $(if ($Success) { 'OK' } else { 'FAIL' })
        Check = $Check
        Detail = $Detail
    })
}

$wazuh = Get-Service -Name 'WazuhSvc' -ErrorAction SilentlyContinue
Add-Result 'Wazuh service' ($null -ne $wazuh -and $wazuh.Status -eq 'Running') $(if ($null -eq $wazuh) { 'missing' } else { $wazuh.Status.ToString() })

$sysmon = Get-Service -Name 'Sysmon64', 'Sysmon' -ErrorAction SilentlyContinue | Select-Object -First 1
Add-Result 'Sysmon service' ($null -ne $sysmon -and $sysmon.Status -eq 'Running') $(if ($null -eq $sysmon) { 'missing' } else { $sysmon.Status.ToString() })

foreach ($port in 1514, 1515) {
    $reachable = Test-NetConnection -ComputerName $ManagerAddress -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue
    Add-Result "Manager TCP $port" $reachable "$ManagerAddress`:$port"
}

$probeDirectory = 'C:\SanoliFood\Quality\Config'
New-Item -ItemType Directory -Force -Path $probeDirectory | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString('o')
Write-Host "STIMULUS_STARTED_AT=$timestamp"
$probePath = Join-Path $probeDirectory 'validation-probe.txt'
Set-Content -LiteralPath $probePath -Value @(
    "SanoliFood endpoint validation $timestamp"
    "run_id=$RunId"
) -Encoding UTF8
Add-Result 'FIM probe' (Test-Path -LiteralPath $probePath) $probePath

$marker = "SanoliFoodEndpointValidation-$RunId"
Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', "echo $marker > NUL") -Wait
Start-Sleep -Seconds 5

$sysmonEvent = Get-WinEvent -FilterHashtable @{
    LogName = 'Microsoft-Windows-Sysmon/Operational'
    Id = 1
    StartTime = (Get-Date).AddMinutes(-5)
} -ErrorAction SilentlyContinue | Where-Object { $_.Message -like "*$marker*" } | Select-Object -First 1
Add-Result 'Sysmon process probe' ($null -ne $sysmonEvent) $(if ($null -eq $sysmonEvent) { 'event not found' } else { "record=$($sysmonEvent.RecordId)" })

$reportDirectory = Join-Path $env:ProgramData 'SanoliFood\Endpoint'
$reportPath = Join-Path $reportDirectory 'validation-result.txt'
New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
$report = $results | Format-Table -AutoSize | Out-String
$report | Write-Host
@(
    "validated_at_utc=$((Get-Date).ToUniversalTime().ToString('o'))",
    $report.TrimEnd()
) | Set-Content -LiteralPath $reportPath -Encoding UTF8
if ($results.Status -contains 'FAIL') {
    Write-Host "Report: $reportPath"
    exit 1
}

Write-Host 'PASS local Windows endpoint checks completed.'
Write-Host "Evaluation ID: $RunId"
Write-Host "Report: $reportPath"
Write-Host 'Allow up to 30 seconds, then run make endpoint-check-live on the SOC host.'
