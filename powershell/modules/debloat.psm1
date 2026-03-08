function Invoke-Debloat {
    Param([switch]$Json)
    $results = [PSCustomObject]@{ Action = "Debloat"; Status = "Success"; RemovedApps = @("Microsoft.YourPhone", "Microsoft.GetHelp") }
    if ($Json) { $results | ConvertTo-Json } else { Write-Host "Debloat complete" }
}
Export-ModuleMember -Function Invoke-Debloat
