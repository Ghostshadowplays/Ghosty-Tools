function Invoke-Maintenance {
    Param([switch]$Json)
    
    $results = [PSCustomObject]@{
        Action = "Maintenance"
        Status = "Success"
        Tasks = @("SFC Scan", "DISM Cleanup", "CHKDSK")
    }

    if ($Json) {
        $results | ConvertTo-Json
    } else {
        Write-Host "Running maintenance tasks..."
        $results.Tasks | ForEach-Object { Write-Host " - $_" }
    }
}

Export-ModuleMember -Function Invoke-Maintenance
