param(
    [Parameter(Mandatory = $true)]
    [string]$ServiceUrl
)

$ErrorActionPreference = "Stop"
$ServiceUrl = $ServiceUrl.TrimEnd("/")
$RequestFile = Join-Path $PSScriptRoot "sample_request.json"

Write-Host "Checking service health..." -ForegroundColor Cyan
curl.exe --fail-with-body "$ServiceUrl/"
if ($LASTEXITCODE -ne 0) { throw "Health check failed." }

Write-Host "`nTriggering ingestion..." -ForegroundColor Cyan
curl.exe --fail-with-body -X POST "$ServiceUrl/load" `
    -H "Content-Type: application/json" `
    --data-binary "@$RequestFile"
if ($LASTEXITCODE -ne 0) { throw "Load request failed." }

Write-Host "`nReading recent audits..." -ForegroundColor Cyan
curl.exe --fail-with-body "$ServiceUrl/audit?limit=5"
if ($LASTEXITCODE -ne 0) { throw "Audit request failed." }
