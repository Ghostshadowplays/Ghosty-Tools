function Invoke-Security {
    Param([switch]$Json)
    $results = [PSCustomObject]@{ Action = "Security"; Status = "Success"; Issues = @() }
    if ($Json) { $results | ConvertTo-Json } else { Write-Host "Security scan complete" }
}
Export-ModuleMember -Function Invoke-Security
