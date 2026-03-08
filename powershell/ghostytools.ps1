# GhostyTools PowerShell Backend
# Version: v5.1.0

Param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("Version", "SystemInfo", "Maintenance", "Debloat", "Security", "Updates", "GUI")]
    [string]$Action = "GUI",

    [Parameter(Mandatory=$false)]
    [switch]$Json = $false,

    [Parameter(Mandatory=$false)]
    [string]$Message = ""
)

$Global:GhostyVersion = "v5.1.0"

# WinForms Helper (for the CTT-style GUI)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Show-GhostyGUI {
    $Form = New-Object System.Windows.Forms.Form
    $Form.Text = "Ghosty Tools v$Global:GhostyVersion"
    $Form.Size = New-Object System.Drawing.Size(600, 450)
    $Form.StartPosition = "CenterScreen"
    $Form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
    $Form.ForeColor = [System.Drawing.Color]::White

    $Title = New-Object System.Windows.Forms.Label
    $Title.Text = "GHOSTY TOOLS"
    $Title.Font = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Bold)
    $Title.Location = New-Object System.Drawing.Point(0, 20)
    $Title.Size = New-Object System.Drawing.Size(600, 50)
    $Title.TextAlign = "MiddleCenter"
    $Form.Controls.Add($Title)

    $BtnWidth = 250
    $BtnHeight = 45
    $LeftPos = 40
    $RightPos = 310

    # System Info
    $BtnSysInfo = New-Object System.Windows.Forms.Button
    $BtnSysInfo.Text = "System Information"
    $BtnSysInfo.Location = New-Object System.Drawing.Point($LeftPos, 100)
    $BtnSysInfo.Size = New-Object System.Drawing.Size($BtnWidth, $BtnHeight)
    $BtnSysInfo.FlatStyle = "Flat"
    $BtnSysInfo.Add_Click({
        $info = Get-GhostySystemInfo
        [System.Windows.Forms.MessageBox]::Show($info | Out-String, "System Info")
    })
    $Form.Controls.Add($BtnSysInfo)

    # Maintenance
    $BtnMaint = New-Object System.Windows.Forms.Button
    $BtnMaint.Text = "Run Maintenance"
    $BtnMaint.Location = New-Object System.Drawing.Point($RightPos, 100)
    $BtnMaint.Size = New-Object System.Drawing.Size($BtnWidth, $BtnHeight)
    $BtnMaint.FlatStyle = "Flat"
    $BtnMaint.Add_Click({
        Invoke-Maintenance
        [System.Windows.Forms.MessageBox]::Show("Maintenance Tasks Completed!", "Success")
    })
    $Form.Controls.Add($BtnMaint)

    # Security
    $BtnSec = New-Object System.Windows.Forms.Button
    $BtnSec.Text = "Security Check"
    $BtnSec.Location = New-Object System.Drawing.Point($LeftPos, 160)
    $BtnSec.Size = New-Object System.Drawing.Size($BtnWidth, $BtnHeight)
    $BtnSec.FlatStyle = "Flat"
    $BtnSec.Add_Click({
        Invoke-Security
        [System.Windows.Forms.MessageBox]::Show("Security Scan Finished!", "Security")
    })
    $Form.Controls.Add($BtnSec)

    # Debloat
    $BtnDebloat = New-Object System.Windows.Forms.Button
    $BtnDebloat.Text = "Debloat System"
    $BtnDebloat.Location = New-Object System.Drawing.Point($RightPos, 160)
    $BtnDebloat.Size = New-Object System.Drawing.Size($BtnWidth, $BtnHeight)
    $BtnDebloat.FlatStyle = "Flat"
    $BtnDebloat.Add_Click({
        Invoke-Debloat
        [System.Windows.Forms.MessageBox]::Show("Debloat operation finished!", "Debloat")
    })
    $Form.Controls.Add($BtnDebloat)

    # Updates
    $BtnUpdates = New-Object System.Windows.Forms.Button
    $BtnUpdates.Text = "Check Updates"
    $BtnUpdates.Location = New-Object System.Drawing.Point($LeftPos, 220)
    $BtnUpdates.Size = New-Object System.Drawing.Size($BtnWidth, $BtnHeight)
    $BtnUpdates.FlatStyle = "Flat"
    $BtnUpdates.Add_Click({
        Invoke-GhostyUpdates
        [System.Windows.Forms.MessageBox]::Show("Update check complete!", "Updates")
    })
    $Form.Controls.Add($BtnUpdates)

    # Launch Python GUI (Full Version)
    $BtnFull = New-Object System.Windows.Forms.Button
    $BtnFull.Text = "Launch Full Python GUI"
    $BtnFull.Location = New-Object System.Drawing.Point($RightPos, 220)
    $BtnFull.Size = New-Object System.Drawing.Size($BtnWidth, $BtnHeight)
    $BtnFull.BackColor = [System.Drawing.Color]::Purple
    $BtnFull.FlatStyle = "Flat"
    $BtnFull.Add_Click({
        Write-Host "Downloading/Launching Full Python Suite..."
        # Future: Add logic to download and run the EXE from GitHub
        [System.Windows.Forms.MessageBox]::Show("This will launch the full Python/Qt version in the next update!", "Info")
    })
    $Form.Controls.Add($BtnFull)

    # Footer
    $Footer = New-Object System.Windows.Forms.Label
    $Footer.Text = "Running in Lite (PowerShell) Mode"
    $Footer.Location = New-Object System.Drawing.Point(0, 370)
    $Footer.Size = New-Object System.Drawing.Size(600, 30)
    $Footer.TextAlign = "MiddleCenter"
    $Footer.ForeColor = [System.Drawing.Color]::Gray
    $Form.Controls.Add($Footer)

    # Import modules before showing
    Get-ChildItem -Path (Join-Path $PSScriptRoot "modules") -Filter *.psm1 | ForEach-Object { Import-Module $_.FullName -ErrorAction SilentlyContinue }

    $Form.ShowDialog()
}

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
    "GUI" {
        Show-GhostyGUI
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
