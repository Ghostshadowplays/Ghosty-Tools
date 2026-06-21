# Ghosty Tools - Universal PowerShell Edition
# Version: 6.7
# Hosted at: https://ghostyware.com

Param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("Version", "SystemInfo", "Maintenance", "Debloat", "Security", "Updates", "GUI")]
    [string]$Action = "GUI",

    [Parameter(Mandatory=$false)]
    [switch]$Json = $false
)

$Global:GhostyVersion = "6.7"
$Global:GhostyUrl = "https://ghostyware.com"

# --- HELPER FUNCTIONS ---
function Show-GhostyHeader {
    if ($Json) { return }
    Clear-Host
Write-Host " +--------------------------------------------------------------------------------------+" -ForegroundColor Magenta
Write-Host " | ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗██╗   ██╗██╗    ██╗ █████╗ ██████╗ ███████╗|" -ForegroundColor Magenta
Write-Host " |██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝╚██╗ ██╔╝██║    ██║██╔══██╗██╔══██╗██╔════╝|" -ForegroundColor Magenta
Write-Host " |██║  ███╗███████║██║   ██║███████╗   ██║    ╚████╔╝ ██║ █╗ ██║███████║██████╔╝█████╗  |" -ForegroundColor Magenta
Write-Host " |██║   ██║██╔══██║██║   ██║╚════██║   ██║     ╚██╔╝  ██║███╗██║██╔══██║██╔══██╗██╔══╝  |" -ForegroundColor Magenta
Write-Host " |╚██████╔╝██║  ██║╚██████╔╝███████║   ██║      ██║   ╚███╔███╔╝██║  ██║██║  ██║███████╗|" -ForegroundColor Magenta
Write-Host " | ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝      ╚═╝    ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝|" -ForegroundColor Magenta
Write-Host " |                 GHOSTY TOOLS UNIVERSAL EDITION v$Global:GhostyVersion                                  |" -ForegroundColor Magenta
Write-Host " +--------------------------------------------------------------------------------------+" -ForegroundColor Magenta
Write-Host "                Official Site: $Global:GhostyUrl" -ForegroundColor DarkGray
Write-Host ""
}

function Check-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
# --- MODULES START ---

function Get-GhostySystemInfo {
    Param([switch]$Json)
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor
    $disk = Get-PhysicalDisk | Where-Object { $_.BusType -eq "NVMe" -or $_.BusType -eq "SSD" -or $_.BusType -eq "SATA" } | Select-Object -First 1
    
    $info = [PSCustomObject]@{
        OS = $os.Caption
        Version = $os.Version
        Manufacturer = $cs.Manufacturer
        Model = $cs.Model
        CPU = $cpu.Name
        Cores = $cpu.NumberOfCores
        TotalMemoryGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
        Disk = "$($disk.FriendlyName) ($([math]::Round($disk.Size / 1GB, 2)) GB)"
        AdminPrivileges = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    if ($Json) { $info | ConvertTo-Json } else { $info | Format-List }
}

function Get-GhostyLiveStats {
    try {
        $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
        $mem = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory
        $memPercent = [math]::Round((($mem.TotalVisibleMemorySize - $mem.FreePhysicalMemory) / $mem.TotalVisibleMemorySize) * 100, 1)
        return @{ CPU = $cpu; RAM = $memPercent }
    } catch { return @{ CPU = 0; RAM = 0 } }
}

function New-SecurePassword {
    param($Length=16, $Upper=$true, $Digits=$true, $Special=$true)
    $chars = "abcdefghijklmnopqrstuvwxyz"
    if ($Upper) { $chars += "ABCDEFGHIJKLMNOPQRSTUVWXYZ" }
    if ($Digits) { $chars += "0123456789" }
    if ($Special) {
        $SpecialChars = '!@#$%^&*()_+-=[]{};'':\",.<>/?|'
        $chars += $SpecialChars
    }
    $password = ""
    for ($i=0; $i -lt $Length; $i++) {
        $password += $chars[(Get-Random -Minimum 0 -Maximum $chars.Length)]
    }
    return $password
}

function Invoke-WingetInstall {
    param($PackageId)
    $process = Start-Process winget -ArgumentList "install --id $PackageId -e --silent --accept-source-agreements --accept-package-agreements" -Wait -PassThru -WindowStyle Hidden
    return $process.ExitCode -eq 0
}

function Invoke-Maintenance {
    Param([switch]$Json)
    $results = @()
    if (-not (Check-Admin)) {
        if ($Json) { return @{ Error = "Elevation Required" } | ConvertTo-Json }
        Write-Host "[!] Error: Maintenance requires Administrator privileges." -ForegroundColor Red
        return
    }

    $tasks = @(
        @{ Name = "DNS Flush"; Command = "ipconfig /flushdns" },
        @{ Name = "Winsock Reset"; Command = "netsh winsock reset" },
        @{ Name = "DISM CheckHealth"; Command = "DISM.exe /Online /Cleanup-Image /CheckHealth" },
        @{ Name = "DISM ScanHealth"; Command = "DISM.exe /Online /Cleanup-Image /ScanHealth" },
        @{ Name = "DISM RestoreHealth"; Command = "DISM.exe /Online /Cleanup-Image /RestoreHealth" },
        @{ Name = "SFC Scan"; Command = "sfc /scannow" },
        @{ Name = "GPUpdate"; Command = "gpupdate /force" },
        @{ Name = "Clear Temp Files"; Command = "Remove-Item -Path $env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue" }
    )
    if (-not $Json) { Write-Host "[*] Starting Ghosty Maintenance..." -ForegroundColor Magenta }
    foreach ($task in $tasks) {
        if (-not $Json) { Write-Host " -> Running $($task.Name)..." -NoNewline }
        $process = Start-Process powershell -ArgumentList "-NoProfile -Command $($task.Command)" -Wait -PassThru -WindowStyle Hidden
        $status = if ($process.ExitCode -eq 0) { "Success" } else { "Failed" }
        $results += [PSCustomObject]@{ Task = $task.Name; Status = $status; ExitCode = $process.ExitCode }
        if (-not $Json) {
            if ($status -eq "Success") { Write-Host " [DONE]" -ForegroundColor Green } else { Write-Host " [FAIL]" -ForegroundColor Red }
        }
    }
    if ($Json) { $results | ConvertTo-Json } else { Write-Host "[+] Maintenance completed." -ForegroundColor Green }
}

function Invoke-Security {
    Param([switch]$Json)
    $results = @()
    $defender = Get-MpComputerStatus
    $results += [PSCustomObject]@{ Issue = "Windows Defender"; Status = if ($defender.AntivirusEnabled -and $defender.RealTimeProtectionEnabled) { "Enabled" } else { "Disabled/Partial" }; Severity = if ($defender.AntivirusEnabled -and $defender.RealTimeProtectionEnabled) { "Low" } else { "High" } }
    $firewall = netsh advfirewall show allprofiles state
    $firewallStatus = if ($firewall -match "OFF") { "Disabled" } else { "Enabled" }
    $results += [PSCustomObject]@{ Issue = "Windows Firewall"; Status = $firewallStatus; Severity = if ($firewallStatus -eq "Enabled") { "Low" } else { "Critical" } }
    $uac = (Get-ItemProperty HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System).EnableLUA
    $results += [PSCustomObject]@{ Issue = "UAC"; Status = if ($uac -eq 1) { "Enabled" } else { "Disabled" }; Severity = if ($uac -eq 1) { "Low" } else { "High" } }
    $smb = Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol
    $results += [PSCustomObject]@{ Issue = "SMBv1"; Status = $smb.State; Severity = if ($smb.State -eq "Enabled") { "High" } else { "Low" } }
    $shares = net share | Where-Object { $_ -and $_ -notmatch "^Share name|^-|^The command completed" -and $_ -notmatch "\$" }
    $results += [PSCustomObject]@{ Issue = "Network Shares"; Status = if ($shares) { "$($shares.Count) Active Shares" } else { "No Public Shares" }; Severity = "Low" }
    if ($Json) { $results | ConvertTo-Json } else { Write-Host "Ghosty Security Scan Results:" -ForegroundColor Cyan; $results | Format-Table -AutoSize }
}

function Invoke-Debloat {
    Param([switch]$Json, [string[]]$Apps)
    if (-not (Check-Admin)) {
        if ($Json) { return @{ Error = "Elevation Required" } | ConvertTo-Json }
        Write-Host "[!] Error: Debloat requires Administrator privileges." -ForegroundColor Red
        return
    }
    
    $appsToRemove = if ($Apps) { $Apps } else { @("Microsoft.YourPhone", "Microsoft.GetHelp", "Microsoft.Getstarted", "Microsoft.Messaging", "Microsoft.3DBuilder", "Microsoft.BingNews", "Microsoft.BingWeather", "Microsoft.MicrosoftSolitaireCollection", "Microsoft.Office.OneNote", "Microsoft.People", "Microsoft.SkypeApp", "Microsoft.WindowsAlarms", "Microsoft.WindowsMaps", "Microsoft.ZuneVideo", "Microsoft.ZuneMusic", "microsoft.windowscommunicationsapps") }
    
    $results = @()
    if (-not $Json) { Write-Host "[*] Starting Ghosty Debloat..." -ForegroundColor Magenta }
    foreach ($app in $appsToRemove) {
        if (-not $Json) { Write-Host " -> Checking $app..." -NoNewline }
        $package = Get-AppxPackage -Name $app -AllUsers
        if ($package) {
            try {
                Remove-AppxPackage -Package $package -ErrorAction Stop
                if (-not $Json) { Write-Host " [REMOVED]" -ForegroundColor Green }
                $results += [PSCustomObject]@{ App = $app; Status = "Removed" }
            } catch {
                if (-not $Json) { Write-Host " [ERROR]" -ForegroundColor Red }
                $results += [PSCustomObject]@{ App = $app; Status = "Failed"; Error = $_.Exception.Message }
            }
        } else {
            if (-not $Json) { Write-Host " [CLEAN]" -ForegroundColor Gray }
        }
    }
    if ($Json) { $results | ConvertTo-Json } else { Write-Host "[+] Debloat operation finished!" -ForegroundColor Green }
}

function Invoke-GhostyUpdates {
    Param([switch]$Json)
    $latestVersion = "0.0"
    try {
        $latestVersion = (Invoke-WebRequest -Uri "$Global:GhostyUrl/static/ps_version.txt" -UseBasicParsing -ErrorAction SilentlyContinue).Content.Trim()
    } catch { }

    $hasNewer = $false
    try {
        if ([version]$latestVersion -gt [version]$Global:GhostyVersion) { $hasNewer = $true }
    } catch {
        if ($latestVersion -ne "0.0" -and $latestVersion -gt $Global:GhostyVersion) { $hasNewer = $true }
    }

    $res = [PSCustomObject]@{
        Current = $Global:GhostyVersion
        Latest = $latestVersion
        UpToDate = (-not $hasNewer)
    }

    if ($Json) { $res | ConvertTo-Json } else {
        if ($hasNewer) {
            Write-Host "[!] New version available: $latestVersion (Current: $Global:GhostyVersion)" -ForegroundColor Yellow
            Write-Host "[!] Visit $Global:GhostyUrl to update." -ForegroundColor Yellow
        } else {
            Write-Host "[+] You are up to date (v$Global:GhostyVersion)" -ForegroundColor Green
        }
    }
}

function Invoke-AdvancedTweak {
    param($Id)
    try {
        switch ($Id) {
            "disable_telemetry" {
                Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name "AllowTelemetry" -Value 0 -Force
                Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name "MaxTelemetryAllowed" -Value 0 -Force
            }
            "disable_copilot" {
                $path1 = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot"
                if (-not (Test-Path $path1)) { New-Item -Path $path1 -Force }
                Set-ItemProperty -Path $path1 -Name "TurnOffWindowsCopilot" -Value 1 -Force
                Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "ShowCopilotButton" -Value 0 -Force
            }
            "classic_context_menu" {
                $clsid = "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
                if (-not (Test-Path $clsid)) { New-Item -Path $clsid -Force }
                Set-ItemProperty -Path $clsid -Name "(Default)" -Value "" -Force
            }
            "disable_web_search" {
                Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" -Name "BingSearchEnabled" -Value 0 -Force
                Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" -Name "CortanaConsent" -Value 0 -Force
            }
            "show_file_ext" {
                Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "HideFileExt" -Value 0 -Force
            }
            "show_hidden" {
                Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "Hidden" -Value 1 -Force
                Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "ShowSuperHidden" -Value 1 -Force
            }
            "ultimate_performance" {
                powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61
                powercfg -setactive e9a42b02-d5df-448d-aa00-03f14749eb61
            }
            "disable_hibernation" {
                powercfg -h off
            }
        }
        return $true
    } catch { return $false }
}

# --- MODULES END ---

# --- GUI LOGIC ---
function Show-GhostyGUI {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $Form = New-Object System.Windows.Forms.Form
    $Form.Text = "Ghostyware Pro v$Global:GhostyVersion"
    $Form.Size = New-Object System.Drawing.Size(1100, 750)
    $Form.StartPosition = "CenterScreen"
    $Form.BackColor = [System.Drawing.Color]::FromArgb(18, 18, 18)
    $Form.ForeColor = [System.Drawing.Color]::White
    $Form.FormBorderStyle = "None"
    $Form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
    $Form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

    # --- THEME COLORS ---
    $ColorPrimary = [System.Drawing.Color]::FromArgb(143, 0, 179) # #8f00b3
    $ColorAccent = [System.Drawing.Color]::FromArgb(191, 0, 240)
    $ColorSidebar = [System.Drawing.Color]::FromArgb(12, 12, 12)
    $ColorMain = [System.Drawing.Color]::FromArgb(18, 18, 18)
    $ColorCard = [System.Drawing.Color]::FromArgb(25, 25, 25)
    $ColorHover = [System.Drawing.Color]::FromArgb(45, 45, 45)

    # --- CUSTOM DRAGGING ---
    $Dragging = $false; $MousePos = New-Object System.Drawing.Point
    $DragAction = {
        if ($script:Dragging) {
            $diff = [System.Drawing.Point]::Subtract([System.Windows.Forms.Control]::MousePosition, $script:MousePos)
            $Form.Location = [System.Drawing.Point]::Add($Form.Location, $diff)
            $script:MousePos = [System.Windows.Forms.Control]::MousePosition
        }
    }

    # --- LOGGING ---
    $LogToTerminal = {
        param($m, $c="LightGray")
        if ($script:TerminalOutput) {
            $timestamp = Get-Date -Format "HH:mm:ss"
            $script:TerminalOutput.Invoke([Action[string, System.Drawing.Color]]{
                param($msg, $clr)
                $this.SelectionStart = $this.TextLength
                $this.SelectionColor = [System.Drawing.Color]::DimGray
                $this.AppendText("[$timestamp] ")
                $this.SelectionColor = $clr
                $this.AppendText("$msg`r`n")
                $this.SelectionStart = $this.Text.Length
                $this.ScrollToCaret()
            }, $m, $c)
        }
    }

    # --- TOP HEADER ---
    $Header = New-Object System.Windows.Forms.Panel
    $Header.Dock = "Top"
    $Header.Height = 80
    $Header.BackColor = $ColorSidebar

    $Header.Add_MouseDown({ $script:Dragging = $true; $script:MousePos = [System.Windows.Forms.Control]::MousePosition })
    $Header.Add_MouseMove($DragAction)
    $Header.Add_MouseUp({ $script:Dragging = $false })

    # Logo Area
    $LogoBox = New-Object System.Windows.Forms.Panel
    $LogoBox.Dock = "Left"
    $LogoBox.Width = 200
    $Header.Controls.Add($LogoBox)
    $LogoBox.Add_MouseDown({ $script:Dragging = $true; $script:MousePos = [System.Windows.Forms.Control]::MousePosition })
    $LogoBox.Add_MouseMove($DragAction)
    $LogoBox.Add_MouseUp({ $script:Dragging = $false })

    $LogoLabel = New-Object System.Windows.Forms.Label
    $LogoLabel.Text = "GHOSTYWARE"
    $LogoLabel.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
    $LogoLabel.ForeColor = $ColorPrimary
    $LogoLabel.Dock = "Fill"
    $LogoLabel.TextAlign = "MiddleCenter"
    $LogoBox.Controls.Add($LogoLabel)
    $LogoLabel.Add_MouseDown({ $script:Dragging = $true; $script:MousePos = [System.Windows.Forms.Control]::MousePosition })
    $LogoLabel.Add_MouseMove($DragAction)
    $LogoLabel.Add_MouseUp({ $script:Dragging = $false })

    $LogoPath = Join-Path $env:TEMP "ghosty_logo_lite.png"
    if (Test-Path $LogoPath) {
        try {
            $Img = [System.Drawing.Image]::FromFile($LogoPath)
            $LogoImg = New-Object System.Windows.Forms.PictureBox
            $LogoImg.Image = $Img; $LogoImg.SizeMode = "Zoom"; $LogoImg.Dock = "Fill"
            $LogoImg.Add_MouseDown({ $script:Dragging = $true; $script:MousePos = [System.Windows.Forms.Control]::MousePosition })
            $LogoImg.Add_MouseMove($DragAction)
            $LogoImg.Add_MouseUp({ $script:Dragging = $false })
            $LogoLabel.Visible = $false
            $LogoBox.Controls.Add($LogoImg)
        } catch {}
    }

    # Window Controls (Close, Min)
    $ControlBox = New-Object System.Windows.Forms.Panel
    $ControlBox.Dock = "Right"
    $ControlBox.Width = 100
    $Header.Controls.Add($ControlBox)

    $BtnClose = New-Object System.Windows.Forms.Button
    $BtnClose.Text = [char]0x2715
    $BtnClose.Size = New-Object System.Drawing.Size(45, 35)
    $BtnClose.Location = New-Object System.Drawing.Point(50, 0)
    $BtnClose.FlatStyle = "Flat"; $BtnClose.FlatAppearance.BorderSize = 0; $BtnClose.ForeColor = [System.Drawing.Color]::White
    $BtnClose.Add_Click({ $Form.Close() })
    $BtnClose.Add_MouseEnter({ $BtnClose.BackColor = [System.Drawing.Color]::DarkRed })
    $BtnClose.Add_MouseLeave({ $BtnClose.BackColor = [System.Drawing.Color]::Transparent })
    $ControlBox.Controls.Add($BtnClose)

    $BtnMin = New-Object System.Windows.Forms.Button
    $BtnMin.Text = [char]0x2014
    $BtnMin.Size = New-Object System.Drawing.Size(45, 35)
    $BtnMin.Location = New-Object System.Drawing.Point(5, 0)
    $BtnMin.FlatStyle = "Flat"; $BtnMin.FlatAppearance.BorderSize = 0; $BtnMin.ForeColor = [System.Drawing.Color]::White
    $BtnMin.Add_Click({ $Form.WindowState = "Minimized" })
    $BtnMin.Add_MouseEnter({ $BtnMin.BackColor = $ColorHover })
    $BtnMin.Add_MouseLeave({ $BtnMin.BackColor = [System.Drawing.Color]::Transparent })
    $ControlBox.Controls.Add($BtnMin)

    # Tabs Panel (Top Nav)
    $TabsContainer = New-Object System.Windows.Forms.FlowLayoutPanel
    $TabsContainer.Dock = "Fill"
    $TabsContainer.FlowDirection = "LeftToRight"
    $TabsContainer.Padding = New-Object System.Windows.Forms.Padding(10, 20, 10, 0)
    $Header.Controls.Add($TabsContainer)
    $TabsContainer.Add_MouseDown({ $script:Dragging = $true; $script:MousePos = [System.Windows.Forms.Control]::MousePosition })
    $TabsContainer.Add_MouseMove($DragAction)
    $TabsContainer.Add_MouseUp({ $script:Dragging = $false })

    # --- SIDEBAR (Quick Actions) ---
    $Sidebar = New-Object System.Windows.Forms.Panel
    $Sidebar.Dock = "Left"
    $Sidebar.Width = 220
    $Sidebar.BackColor = $ColorSidebar
    $Sidebar.Padding = New-Object System.Windows.Forms.Padding(15)
    $Form.Controls.Add($Sidebar)
    $Form.Controls.Add($Header)

    $SideTitle = New-Object System.Windows.Forms.Label
    $SideTitle.Text = "QUICK ACTIONS"
    $SideTitle.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
    $SideTitle.ForeColor = [System.Drawing.Color]::DimGray
    $SideTitle.Dock = "Top"
    $SideTitle.Height = 40
    $Sidebar.Controls.Add($SideTitle)

    # --- MAIN CONTENT ---
    $MainPanel = New-Object System.Windows.Forms.Panel
    $MainPanel.Dock = "Fill"
    $MainPanel.BackColor = $ColorMain
    $MainPanel.Padding = New-Object System.Windows.Forms.Padding(40, 20, 40, 20)
    $Form.Controls.Add($MainPanel)

    # Title
    $ContentTitle = New-Object System.Windows.Forms.Label
    $ContentTitle.Font = New-Object System.Drawing.Font("Segoe UI", 28, [System.Drawing.FontStyle]::Bold)
    $ContentTitle.ForeColor = $ColorPrimary
    $ContentTitle.Dock = "Top"
    $ContentTitle.Height = 80
    $ContentTitle.TextAlign = "MiddleLeft"
    $MainPanel.Controls.Add($ContentTitle)

    # Scroll container
    $ContentScroll = New-Object System.Windows.Forms.Panel
    $ContentScroll.Dock = "Fill"
    $ContentScroll.AutoScroll = $true
    $MainPanel.Controls.Add($ContentScroll)

    # Flow layout inside scroll panel
    $ContentArea = New-Object System.Windows.Forms.FlowLayoutPanel
    $ContentArea.Dock = "Top"
    $ContentArea.WrapContents = $true
    $ContentArea.AutoSize = $true
    $ContentArea.AutoSizeMode = "GrowAndShrink"
    $ContentArea.FlowDirection = "LeftToRight"
    $ContentArea.Padding = New-Object System.Windows.Forms.Padding(0,0,0,0)
    $ContentScroll.Controls.Add($ContentArea)

    # Terminal at bottom
    $TerminalContainer = New-Object System.Windows.Forms.GroupBox
    $TerminalContainer.Text = "LIVE TERMINAL FEED"
    $TerminalContainer.Dock = "Bottom"
    $TerminalContainer.Height = 160
    $TerminalContainer.ForeColor = $ColorPrimary
    $TerminalContainer.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Bold)
    $MainPanel.Controls.Add($TerminalContainer)

    $script:TerminalOutput = New-Object System.Windows.Forms.RichTextBox
    $script:TerminalOutput.Dock = "Fill"
    $script:TerminalOutput.ReadOnly = $true
    $script:TerminalOutput.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 25)
    $script:TerminalOutput.ForeColor = [System.Drawing.Color]::LightGray
    $script:TerminalOutput.BorderStyle = "None"
    $script:TerminalOutput.Font = New-Object System.Drawing.Font("Consolas", 9)
    $TerminalContainer.Controls.Add($script:TerminalOutput)

    # --- HELPERS ---
    $LastActiveTab = $null

    function Set-Tab($Btn, $Title, $Action) {
        if ($LastActiveTab) { 
            $LastActiveTab.BackColor = [System.Drawing.Color]::Transparent
            $LastActiveTab.ForeColor = [System.Drawing.Color]::Gray 
        }
        $Btn.BackColor = $ColorCard
        $Btn.ForeColor = [System.Drawing.Color]::White
        $script:LastActiveTab = $Btn
        
        $ContentTitle.Text = $Title
        $ContentArea.Controls.Clear()
        &$Action
    }

    function New-TabButton($Text, $Icon) {
        $Btn = New-Object System.Windows.Forms.Button
        $Btn.Text = "$Icon $Text"
        $Btn.Size = New-Object System.Drawing.Size(140, 45)
        $Btn.FlatStyle = "Flat"; $Btn.FlatAppearance.BorderSize = 0
        $Btn.ForeColor = [System.Drawing.Color]::Gray
        $Btn.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
        $Btn.Cursor = [System.Windows.Forms.Cursors]::Hand
        $Btn.Margin = New-Object System.Windows.Forms.Padding(5, 0, 5, 0)
        $Btn.Add_MouseEnter({ if ($Btn -ne $LastActiveTab) { $Btn.BackColor = $ColorHover } })
        $Btn.Add_MouseLeave({ if ($Btn -ne $LastActiveTab) { $Btn.BackColor = [System.Drawing.Color]::Transparent } })
        $TabsContainer.Controls.Add($Btn)
        return $Btn
    }

    function New-ActionBtn($Text, $Action) {
        $Btn = New-Object System.Windows.Forms.Button
        $Btn.Text = $Text
        $Btn.Dock = "Top"
        $Btn.Height = 45
        $Btn.FlatStyle = "Flat"; $Btn.FlatAppearance.BorderSize = 1; $Btn.FlatAppearance.BorderColor = $ColorCard
        $Btn.ForeColor = [System.Drawing.Color]::LightGray
        $Btn.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 10)
        $Btn.Cursor = [System.Windows.Forms.Cursors]::Hand
        $Btn.Add_Click($Action)
        $Sidebar.Controls.Add($Btn)
        $Btn.BringToFront()
    }

    function New-Card($Title, $Desc, $BtnText, $Action) {
        $Card = New-Object System.Windows.Forms.Panel
        $Card.Size = New-Object System.Drawing.Size(320, 190)
        $Card.BackColor = $ColorCard
        $Card.Margin = New-Object System.Windows.Forms.Padding(0, 0, 25, 25)
        
        $CTitle = New-Object System.Windows.Forms.Label
        $CTitle.Text = $Title
        $CTitle.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
        $CTitle.Location = New-Object System.Drawing.Point(20, 20)
        $CTitle.Size = New-Object System.Drawing.Size(280, 30)
        $CTitle.ForeColor = $ColorAccent
        $Card.Controls.Add($CTitle)

        $CDesc = New-Object System.Windows.Forms.Label
        $CDesc.Text = $Desc
        $CDesc.Font = New-Object System.Drawing.Font("Segoe UI", 9)
        $CDesc.Location = New-Object System.Drawing.Point(20, 55)
        $CDesc.Size = New-Object System.Drawing.Size(280, 65)
        $CDesc.ForeColor = [System.Drawing.Color]::DarkGray
        $Card.Controls.Add($CDesc)

        $CBtn = New-Object System.Windows.Forms.Button
        $CBtn.Text = $BtnText
        $CBtn.Location = New-Object System.Drawing.Point(20, 130)
        $CBtn.Size = New-Object System.Drawing.Size(280, 40)
        $CBtn.FlatStyle = "Flat"; $CBtn.BackColor = $ColorHover; $CBtn.FlatAppearance.BorderSize = 0
        $CBtn.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
        $CBtn.Add_Click($Action)
        $Card.Controls.Add($CBtn)

        $ContentArea.Controls.Add($Card)
    }

    # --- PAGES ---
    $ShowHome = {
        $script:StatsLabel = New-Object System.Windows.Forms.Label
        $script:StatsLabel.Text = "CPU: ... | RAM: ..."
        $script:StatsLabel.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
        $script:StatsLabel.ForeColor = [System.Drawing.Color]::White
        $script:StatsLabel.Size = New-Object System.Drawing.Size(600, 40)
        $script:StatsLabel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 20)
        $ContentArea.Controls.Add($script:StatsLabel)
        $ContentArea.SetFlowBreak($script:StatsLabel, $true)

        # Timer must be script-scope
        $script:UpdateStatsTimer = New-Object System.Windows.Forms.Timer
        $script:UpdateStatsTimer.Interval = 2000
        $script:UpdateStatsTimer.Add_Tick({
            $stats = Get-GhostyLiveStats
            $script:StatsLabel.Text = "CPU: $($stats.CPU)% | RAM: $($stats.RAM)%"
        })
        $script:UpdateStatsTimer.Start()

        # Stop timer on close
        $Form.Add_FormClosing({ $script:UpdateStatsTimer.Stop() })

        New-Card "System Health" "View a detailed summary of your hardware and OS status." "View Summary" {
            &$LogToTerminal "Gathering system info..." "Cyan"
            $info = Get-GhostySystemInfo
            &$LogToTerminal ($info | Out-String) "LightGray"
            [System.Windows.Forms.MessageBox]::Show(($info | Out-String), "System Summary")
        }

        New-Card "Disk Health" "Check S.M.A.R.T. status and health of your primary drive." "Check Now" {
            &$LogToTerminal "Checking disk health..." "Cyan"
            $health = Get-PhysicalDisk | Select-Object DeviceID, FriendlyName, HealthStatus, OperationalStatus
            &$LogToTerminal ($health | Out-String) "LightGray"
            [System.Windows.Forms.MessageBox]::Show(($health | Out-String), "Disk Health")
        }

        New-Card "Battery Health" "Check battery capacity and wear level (for laptops)." "Check Now" {
            &$LogToTerminal "Checking battery health..." "Cyan"
            $batt = Get-CimInstance Win32_Battery
            if ($batt) {
                &$LogToTerminal ($batt | Out-String) "LightGray"
                [System.Windows.Forms.MessageBox]::Show(($batt | Out-String), "Battery Status")
            } else {
                &$LogToTerminal "No battery detected." "Yellow"
                [System.Windows.Forms.MessageBox]::Show("No battery detected.", "Info")
            }
        }
    }

    $ShowMaintenance = {
        New-Card "System Repair" "Run SFC and DISM to repair corrupted system files." "Run Repair" {
             if (-not (Check-Admin)) { [System.Windows.Forms.MessageBox]::Show("Admin Required", "Error"); return }
             &$LogToTerminal "Starting System Repair (SFC/DISM)..." "Yellow"
             Invoke-Maintenance; 
             &$LogToTerminal "Repair process completed." "Green"
             [System.Windows.Forms.MessageBox]::Show("Optimization Complete!", "Success")
        }
        New-Card "Clean Temp" "Delete temporary files and clear DNS cache." "Clean Now" {
            &$LogToTerminal "Cleaning temporary files and DNS..." "Yellow"
            Remove-Item -Path $env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue
            ipconfig /flushdns
            &$LogToTerminal "Cleanup completed." "Green"
            [System.Windows.Forms.MessageBox]::Show("Cleanup Complete!", "Success")
        }
        New-Card "Disk Cleanup" "Launch the Windows Disk Cleanup utility." "Launch" {
            Start-Process "cleanmgr.exe" -ArgumentList "/d C"
        }
        New-Card "Windows Updates" "Check for pending Windows Updates." "Check Now" {
            &$LogToTerminal "Checking for Windows Updates..." "Cyan"
            try {
                $UpdateSession = New-Object -ComObject Microsoft.Update.Session
                $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
                $SearchResult = $UpdateSearcher.Search("IsInstalled=0 and IsHidden=0")
                &$LogToTerminal "Found $($SearchResult.Updates.Count) pending updates." "Green"
                [System.Windows.Forms.MessageBox]::Show("Found $($SearchResult.Updates.Count) updates.", "Windows Update")
            } catch {
                &$LogToTerminal "Failed to check for updates: $_" "Red"
            }
        }
        New-Card "Disk Convert" "Validate if your disk is ready for MBR2GPT conversion." "Validate" {
             if (-not (Check-Admin)) { [System.Windows.Forms.MessageBox]::Show("Admin Required", "Error"); return }
             &$LogToTerminal "Validating disk for MBR2GPT..." "Yellow"
             $res = mbr2gpt /validate /allowfullos
             &$LogToTerminal ($res | Out-String) "LightGray"
        }
    }

    $ShowSecurity = {
        New-Card "Security Scan" "Audit your firewall, defender, and UAC settings." "Start Scan" {
            &$LogToTerminal "Starting security audit..." "Cyan"
            Invoke-Security; 
            &$LogToTerminal "Audit completed. Review results in the feed above." "Green"
            [System.Windows.Forms.MessageBox]::Show("Scan Complete!", "Security")
        }
        New-Card "UAC Settings" "Manage User Account Control notification level." "Open Settings" {
            Start-Process "UserAccountControlSettings.exe"
        }
    }

    $ShowDebloat = {
        New-Card "Essential Debloat" "Remove common pre-installed bloatware apps." "Start Debloat" {
            if (-not (Check-Admin)) { [System.Windows.Forms.MessageBox]::Show("Admin Required", "Error"); return }
            &$LogToTerminal "Starting Essential Debloat..." "Yellow"
            Invoke-Debloat; 
            &$LogToTerminal "Debloat finished." "Green"
            [System.Windows.Forms.MessageBox]::Show("Debloat Complete!", "Success")
        }
    }

    $ShowTools = {
        $ToolList = @(
            @{ Name = "Git"; Id = "Git.Git" },
            @{ Name = "VS Code"; Id = "Microsoft.VisualStudioCode" },
            @{ Name = "Python"; Id = "Python.Python.3.12" },
            @{ Name = "Node.js"; Id = "OpenJS.NodeJS.LTS" },
            @{ Name = "Discord"; Id = "Discord.Discord" }
        )
        foreach ($tool in $ToolList) {
            New-Card "Install $($tool.Name)" "Install $($tool.Name) using Winget package manager." "Install" {
                &$LogToTerminal "Installing $($tool.Name)..." "Cyan"
                if (Invoke-WingetInstall -PackageId $tool.Id) {
                    &$LogToTerminal "$($tool.Name) installed successfully." "Green"
                } else {
                    &$LogToTerminal "Failed to install $($tool.Name)." "Red"
                }
            }
        }
    }

    $ShowPassGen = {
        $LenLabel = New-Object System.Windows.Forms.Label
        $LenLabel.Text = "Length: 16"; $LenLabel.ForeColor = [System.Drawing.Color]::White
        $ContentArea.Controls.Add($LenLabel)
        
        $Track = New-Object System.Windows.Forms.TrackBar
        $Track.Minimum = 8; $Track.Maximum = 64; $Track.Value = 16; $Track.Width = 200
        $Track.Add_ValueChanged({ $LenLabel.Text = "Length: $($Track.Value)" })
        $ContentArea.Controls.Add($Track)
        $ContentArea.SetFlowBreak($Track, $true)

        $ResultBox = New-Object System.Windows.Forms.TextBox
        $ResultBox.Width = 320; $ResultBox.ReadOnly = $true; $ResultBox.Font = New-Object System.Drawing.Font("Consolas", 12)
        $ContentArea.Controls.Add($ResultBox)
        $ContentArea.SetFlowBreak($ResultBox, $true)

        New-Card "Generate" "Generate a secure, random password." "Generate" {
            $pass = New-SecurePassword -Length $Track.Value
            $ResultBox.Text = $pass
            &$LogToTerminal "Generated new password." "Green"
        }
        New-Card "Copy" "Copy the generated password to clipboard." "Copy" {
            if ($ResultBox.Text) {
                [System.Windows.Forms.Clipboard]::SetText($ResultBox.Text)
                &$LogToTerminal "Password copied to clipboard." "Cyan"
            }
        }
    }

    $ShowTweaks = {
        $TweakList = @(
            @{ Name = "Privacy Pack"; Desc = "Disable Telemetry and Copilot."; Id = "disable_telemetry" },
            @{ Name = "Classic Menu"; Desc = "Restore Win10 Context Menu."; Id = "classic_context_menu" },
            @{ Name = "Performance"; Desc = "Enable Ultimate Performance Plan."; Id = "ultimate_performance" },
            @{ Name = "Show Files"; Desc = "Show hidden files and extensions."; Id = "show_file_ext" }
        )
        foreach ($tw in $TweakList) {
            New-Card $tw.Name $tw.Desc "Apply" {
                &$LogToTerminal "Applying $($tw.Name)..." "Cyan"
                if (Invoke-AdvancedTweak -Id $tw.Id) {
                    &$LogToTerminal "$($tw.Name) applied successfully." "Green"
                } else {
                    &$LogToTerminal "Failed to apply $($tw.Name)." "Red"
                }
            }
        }
    }

    $ShowAbout = {
        $AboutText = New-Object System.Windows.Forms.Label
        $AboutText.Text = "Ghostyware Universal Pro v$Global:GhostyVersion`r`nCreated by Ghostyware Team`r`n`r`nPowered by PowerShell WinForms Engine."
        $AboutText.Font = New-Object System.Drawing.Font("Segoe UI", 12); $AboutText.Size = New-Object System.Drawing.Size(600, 150)
        $AboutText.ForeColor = [System.Drawing.Color]::White
        $ContentArea.Controls.Add($AboutText)
    }

    # --- INITIALIZE TABS ---
    $TabHome = New-TabButton "Dashboard" ([char]::ConvertFromUtf32(0x2302))
    $TabHome.Add_Click({ Set-Tab $TabHome "System Dashboard" $ShowHome })

    $TabMaint = New-TabButton "Maintenance" ([char]::ConvertFromUtf32(0x2699))
    $TabMaint.Add_Click({ Set-Tab $TabMaint "Maintenance" $ShowMaintenance })

    $TabSec = New-TabButton "Security" ([char]::ConvertFromUtf32(0x1F6E1))
    $TabSec.Add_Click({ Set-Tab $TabSec "Security Center" $ShowSecurity })

    $TabDebloat = New-TabButton "Debloat" ([char]::ConvertFromUtf32(0x1F5D1))
    $TabDebloat.Add_Click({ Set-Tab $TabDebloat "System Debloat" $ShowDebloat })

    $TabTools = New-TabButton "Tools" ([char]::ConvertFromUtf32(0x1F6E0))
    $TabTools.Add_Click({ Set-Tab $TabTools "System Tools" $ShowTools })

    $TabPass = New-TabButton "Password" ([char]::ConvertFromUtf32(0x1F512))
    $TabPass.Add_Click({ Set-Tab $TabPass "Password Generator" $ShowPassGen })

    $TabTweaks = New-TabButton "Tweaks" ([char]::ConvertFromUtf32(0x21BB))
    $TabTweaks.Add_Click({ Set-Tab $TabTweaks "Optimizations" $ShowTweaks })

    $TabAbout = New-TabButton "About" ([char]::ConvertFromUtf32(0x2139))
    $TabAbout.Add_Click({ Set-Tab $TabAbout "About Ghosty" $ShowAbout })

    # --- SIDEBAR ACTIONS (Added in reverse order for Dock=Top + BringToFront) ---
    New-ActionBtn "Clear Temp" { Remove-Item -Path $env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue; [System.Windows.Forms.MessageBox]::Show("Temp Cleared!", "Action") }
    New-ActionBtn "SFC Scan" { if (Check-Admin) { Start-Process "sfc" -ArgumentList "/scannow" -Wait } else { [System.Windows.Forms.MessageBox]::Show("Admin Required", "Error") } }
    New-ActionBtn "Flush DNS" { Invoke-Expression "ipconfig /flushdns"; [System.Windows.Forms.MessageBox]::Show("DNS Flushed!", "Action") }
    $SideTitle.BringToFront()

    # Init
    Set-Tab $TabHome "System Dashboard" $ShowHome
    $Form.ShowDialog()
}

# --- MAIN LOGIC ---
Show-GhostyHeader
switch ($Action) {
    "Version"      { if ($Json) { @{ Version = $Global:GhostyVersion } | ConvertTo-Json } else { Write-Host "GhostyTools Version: $Global:GhostyVersion" } }
    "SystemInfo"   { Get-GhostySystemInfo -Json:$Json }
    "Maintenance"  { Invoke-Maintenance -Json:$Json }
    "Debloat"      { Invoke-Debloat -Json:$Json }
    "Security"     { Invoke-Security -Json:$Json }
    "Updates"      { Invoke-GhostyUpdates -Json:$Json }
    "GUI"          { Show-GhostyGUI }
    Default        { if ($Json) { @{ Status = "Success"; Action = $Action } | ConvertTo-Json } else { Write-Host "Action $Action handled." } }
}
