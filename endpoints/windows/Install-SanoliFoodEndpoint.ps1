[CmdletBinding()]
param(
    [string]$ManagerAddress = '10.20.0.10',
    [string]$AgentName = 'sanolifood-win-01',
    [string]$AgentGroup = 'sanolifood-windows',
    [string]$WazuhVersion = '4.14.7',
    [string]$SysmonExpectedVersion = '15.21',
    [string]$SysmonConfigPath = '',
    [switch]$SkipSysmon
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-ValidSignature {
    param([Parameter(Mandatory = $true)][string]$Path)
    $signature = Get-AuthenticodeSignature -FilePath $Path
    if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
        throw "Authenticode validation failed for $Path (status: $($signature.Status))."
    }
}

function Invoke-CheckedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [int[]]$AllowedExitCodes = @(0)
    )
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -Wait -PassThru
    if ($AllowedExitCodes -notcontains $process.ExitCode) {
        throw "$FilePath exited with code $($process.ExitCode)."
    }
    return $process.ExitCode
}

if (-not (Test-Administrator)) {
    throw 'Open PowerShell as Administrator before running this installer.'
}

if ([string]::IsNullOrWhiteSpace($SysmonConfigPath)) {
    $SysmonConfigPath = Join-Path $PSScriptRoot 'config\sysmonconfig.xml'
}
$SysmonConfigPath = [IO.Path]::GetFullPath($SysmonConfigPath)
if (-not $SkipSysmon -and -not (Test-Path -LiteralPath $SysmonConfigPath -PathType Leaf)) {
    throw "Sysmon configuration not found: $SysmonConfigPath"
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$root = Join-Path $env:ProgramData 'SanoliFood\Endpoint'
$packageDir = Join-Path $root 'packages'
$configDir = Join-Path $root 'config'
$manifestPath = Join-Path $root 'install-manifest.txt'
$businessConfigDir = 'C:\SanoliFood\Quality\Config'
New-Item -ItemType Directory -Force -Path $root, $packageDir, $configDir, $businessConfigDir | Out-Null

$qualityPolicySource = Join-Path $PSScriptRoot 'config\quality-policy.json'
if (-not (Test-Path -LiteralPath $qualityPolicySource -PathType Leaf)) {
    throw "Quality policy fixture not found: $qualityPolicySource"
}
Copy-Item -LiteralPath $qualityPolicySource -Destination (Join-Path $businessConfigDir 'quality-policy.json') -Force

$wazuhMsi = Join-Path $packageDir "wazuh-agent-$WazuhVersion-1.msi"
$wazuhUri = "https://packages.wazuh.com/4.x/windows/wazuh-agent-$WazuhVersion-1.msi"
if (-not (Test-Path -LiteralPath $wazuhMsi -PathType Leaf)) {
    Write-Host "Downloading Wazuh agent $WazuhVersion from the official repository..."
    Invoke-WebRequest -Uri $wazuhUri -OutFile $wazuhMsi -UseBasicParsing
}
Assert-ValidSignature -Path $wazuhMsi
$wazuhHash = (Get-FileHash -LiteralPath $wazuhMsi -Algorithm SHA256).Hash

$wazuhService = Get-Service -Name 'WazuhSvc' -ErrorAction SilentlyContinue
if ($null -eq $wazuhService) {
    $securePassword = Read-Host 'Wazuh enrollment password' -AsSecureString
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
        $msiArguments = @(
            '/i',
            "`"$wazuhMsi`"",
            '/qn',
            '/norestart',
            "WAZUH_MANAGER=$ManagerAddress",
            'WAZUH_MANAGER_PORT=1514',
            'WAZUH_PROTOCOL=tcp',
            "WAZUH_REGISTRATION_SERVER=$ManagerAddress",
            'WAZUH_REGISTRATION_PORT=1515',
            "WAZUH_REGISTRATION_PASSWORD=$plainPassword",
            "WAZUH_AGENT_NAME=$AgentName",
            "WAZUH_AGENT_GROUP=$AgentGroup"
        )
        Invoke-CheckedProcess -FilePath 'msiexec.exe' -ArgumentList $msiArguments -AllowedExitCodes @(0, 3010) | Out-Null
    }
    finally {
        if ($passwordPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
        }
        $plainPassword = $null
        $securePassword = $null
    }
} else {
    $agentExecutable = Join-Path ${env:ProgramFiles(x86)} 'ossec-agent\wazuh-agent.exe'
    if (-not (Test-Path -LiteralPath $agentExecutable -PathType Leaf)) {
        throw 'WazuhSvc exists but the expected agent executable is missing.'
    }
    $installedAgentVersion = (Get-Item -LiteralPath $agentExecutable).VersionInfo.ProductVersion
    $normalizedInstalledVersion = $installedAgentVersion.TrimStart([char[]]'vV')
    $normalizedPinnedVersion = $WazuhVersion.TrimStart([char[]]'vV')
    if ($normalizedInstalledVersion -notlike "$normalizedPinnedVersion*") {
        throw "Existing Wazuh agent version $installedAgentVersion does not match pinned version $WazuhVersion."
    }
    Write-Host 'Wazuh agent is already installed; preserving its existing enrollment.'
}

$wazuhService = Get-Service -Name 'WazuhSvc' -ErrorAction Stop
Set-Service -Name $wazuhService.Name -StartupType Automatic
Start-Service -Name $wazuhService.Name -ErrorAction SilentlyContinue

$clientKeys = Join-Path ${env:ProgramFiles(x86)} 'ossec-agent\client.keys'
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline -and
       (-not (Test-Path -LiteralPath $clientKeys -PathType Leaf) -or (Get-Item -LiteralPath $clientKeys).Length -eq 0)) {
    Start-Sleep -Seconds 2
}
if (-not (Test-Path -LiteralPath $clientKeys -PathType Leaf) -or (Get-Item -LiteralPath $clientKeys).Length -eq 0) {
    throw 'The Wazuh agent service started but no enrollment key was created within 60 seconds.'
}

$sysmonHash = 'not-installed'
$sysmonVersion = 'not-installed'
$sysmonConfigHash = 'not-installed'
if (-not $SkipSysmon) {
    $sysmonZip = Join-Path $packageDir 'Sysmon.zip'
    $sysmonExtract = Join-Path $packageDir 'Sysmon'
    if (-not (Test-Path -LiteralPath $sysmonZip -PathType Leaf)) {
        Write-Host 'Downloading Sysmon from Microsoft Sysinternals...'
        Invoke-WebRequest -Uri 'https://download.sysinternals.com/files/Sysmon.zip' -OutFile $sysmonZip -UseBasicParsing
    }
    if (Test-Path -LiteralPath $sysmonExtract) {
        Remove-Item -LiteralPath $sysmonExtract -Recurse -Force
    }
    Expand-Archive -LiteralPath $sysmonZip -DestinationPath $sysmonExtract -Force
    $sysmonExe = Join-Path $sysmonExtract 'Sysmon64.exe'
    Assert-ValidSignature -Path $sysmonExe
    $sysmonHash = (Get-FileHash -LiteralPath $sysmonExe -Algorithm SHA256).Hash
    $sysmonVersion = (Get-Item -LiteralPath $sysmonExe).VersionInfo.FileVersion
    if ($sysmonVersion -notlike "$SysmonExpectedVersion*") {
        throw "Expected Sysmon $SysmonExpectedVersion but the official package reports $sysmonVersion. Review and version the dependency before continuing."
    }
    $sysmonConfigHash = (Get-FileHash -LiteralPath $SysmonConfigPath -Algorithm SHA256).Hash
    Copy-Item -LiteralPath $SysmonConfigPath -Destination (Join-Path $configDir 'sysmonconfig.xml') -Force

    $existingSysmon = Get-Service -Name 'Sysmon64', 'Sysmon' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $existingSysmon) {
        Invoke-CheckedProcess -FilePath $sysmonExe -ArgumentList @('-accepteula', '-i', "`"$SysmonConfigPath`"") | Out-Null
    } else {
        Invoke-CheckedProcess -FilePath $sysmonExe -ArgumentList @('-c', "`"$SysmonConfigPath`"") | Out-Null
    }
    & wevtutil.exe sl 'Microsoft-Windows-Sysmon/Operational' /e:true
}

& wevtutil.exe sl 'Microsoft-Windows-PowerShell/Operational' /e:true
Restart-Service -Name $wazuhService.Name

@(
    "installed_at_utc=$((Get-Date).ToUniversalTime().ToString('o'))",
    "manager=$ManagerAddress",
    "agent_name=$AgentName",
    "agent_group=$AgentGroup",
    "wazuh_version=$WazuhVersion",
    "wazuh_msi_sha256=$wazuhHash",
    "sysmon_version=$sysmonVersion",
    "sysmon_exe_sha256=$sysmonHash",
    "sysmon_config_sha256=$sysmonConfigHash"
) | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host 'PASS SanoliFood Windows endpoint installation completed.'
Write-Host "Agent: $AgentName | Group: $AgentGroup | Manager: $ManagerAddress"
Write-Host "Manifest: $manifestPath"
Write-Host 'No enrollment password was written to the manifest or installation files.'
