# GhostyTools PowerShell Backend
# Version: v5.0.9

Param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("Version", "SystemInfo", "Maintenance", "Debloat", "Security", "Updates")]
    [string]$Action = "Version",

    [Parameter(Mandatory=$false)]
    [switch]$Json = $false,

    [Parameter(Mandatory=$false)]
    [string]$Message = ""
)

$Global:GhostyVersion = "v5.0.9"

# Logging Function
function Write-GhostyLog {
    Param([string]$Message)
    $LogDir = Join-Path $PSScriptRoot "logs"
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
    $LogFile = Join-Path $LogDir "ghostytools.log"
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$Timestamp] $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# Admin Check
function Test-IsAdmin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Main Logic
switch ($Action) {
    "Version" {
        if ($Json) {
            [PSCustomObject]@{
                Version = $Global:GhostyVersion
                Status = "Success"
            } | ConvertTo-Json
        } else {
            Write-Host "GhostyTools Version: $($Global:GhostyVersion)"
        }
    }
    "SystemInfo" {
        $modulePath = Join-Path $PSScriptRoot "modules\systeminfo.psm1"
        if (Test-Path $modulePath) {
            Import-Module $modulePath
            Get-GhostySystemInfo -Json:$Json
        } else {
             if ($Json) { @{Status="Error"; Message="Module systeminfo.psm1 not found"} | ConvertTo-Json } else { Write-Error "SystemInfo module missing" }
        }
    }
    "Maintenance" {
        $modulePath = Join-Path $PSScriptRoot "modules\maintenance.psm1"
        if (Test-Path $modulePath) {
            Import-Module $modulePath
            Invoke-Maintenance -Json:$Json
        } else {
             if ($Json) { @{Status="Error"; Message="Module maintenance.psm1 not found"} | ConvertTo-Json } else { Write-Error "Maintenance module missing" }
        }
    }
    "Debloat" {
        $modulePath = Join-Path $PSScriptRoot "modules\debloat.psm1"
        if (Test-Path $modulePath) {
            Import-Module $modulePath
            Invoke-Debloat -Json:$Json
        } else {
             if ($Json) { @{Status="Error"; Message="Module debloat.psm1 not found"} | ConvertTo-Json } else { Write-Error "Debloat module missing" }
        }
    }
    "Security" {
        $modulePath = Join-Path $PSScriptRoot "modules\security.psm1"
        if (Test-Path $modulePath) {
            Import-Module $modulePath
            Invoke-Security -Json:$Json
        } else {
             if ($Json) { @{Status="Error"; Message="Module security.psm1 not found"} | ConvertTo-Json } else { Write-Error "Security module missing" }
        }
    }
    "Updates" {
        $modulePath = Join-Path $PSScriptRoot "modules\updates.psm1"
        if (Test-Path $modulePath) {
            Import-Module $modulePath
            Invoke-GhostyUpdates -Json:$Json
        } else {
             if ($Json) { @{Status="Error"; Message="Module updates.psm1 not found"} | ConvertTo-Json } else { Write-Error "Updates module missing" }
        }
    }
    Default {
        if ($Json) {
            [PSCustomObject]@{
                Status = "Success"
                Message = "PowerShell backend working"
                Action = $Action
            } | ConvertTo-Json
        } else {
            Write-Host "Action $Action handled. PowerShell backend working."
        }
    }
}
