function Get-GhostySystemInfo {
    Param([switch]$Json)
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem
    $info = [PSCustomObject]@{
        OS = $os.Caption
        Version = $os.Version
        Manufacturer = $cs.Manufacturer
        Model = $cs.Model
        TotalMemoryGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
        AdminPrivileges = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    if ($Json) { $info | ConvertTo-Json } else { $info | Format-List }
}
Export-ModuleMember -Function Get-GhostySystemInfo
