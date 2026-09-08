# --------------------------- Configuration ---------------------------------
$ProjectId = "YOUR_GCP_PROJECT_ID"
$Region = "us-central1"
$Repository = "travel-platform"
$ImageName = "travel-ingestion-api"
$ImageTag = "v1"
$ServiceName = "travel-ingestion-api"
$ServiceAccount = "travel-ingestion-sa@$ProjectId.iam.gserviceaccount.com"
$BucketName = "YOUR_BUCKET_NAME"
$BigQueryDataset = "travel_analytics"
$BigQueryLocation = "US"
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"
$LocalImage = "${ImageName}:${ImageTag}"
$RemoteImage = "${Region}-docker.pkg.dev/${ProjectId}/${Repository}/${ImageName}:${ImageTag}"
$RequestFile = Join-Path $PSScriptRoot "sample_request.json"
$RepoRoot = Split-Path $PSScriptRoot -Parent

function Show-Step([int]$Number, [string]$Message) {
    Write-Host "`n[$Number/7] $Message" -ForegroundColor Cyan
}

function Assert-Success([string]$Message) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Message (exit code $LASTEXITCODE)"
    }
}

if ($ProjectId -like "YOUR_*" -or $BucketName -like "YOUR_*") {
    throw "Set ProjectId and BucketName at the top of scripts/deploy.ps1."
}

Push-Location $RepoRoot
try {
    Show-Step 1 "Pulling the latest Git changes"
    git pull
    Assert-Success "Git pull failed"

    Show-Step 2 "Building Docker image"
    docker build -t $LocalImage .
    Assert-Success "Docker build failed"

    Show-Step 3 "Tagging image for Artifact Registry"
    docker tag $LocalImage $RemoteImage
    Assert-Success "Docker tag failed"

    Show-Step 4 "Pushing image to Artifact Registry"
    gcloud auth configure-docker "${Region}-docker.pkg.dev" --quiet
    Assert-Success "Docker credential configuration failed"
    docker push $RemoteImage
    Assert-Success "Docker push failed"

    Show-Step 5 "Deploying Cloud Run service"
    gcloud run deploy $ServiceName `
        --project $ProjectId `
        --region $Region `
        --image $RemoteImage `
        --service-account $ServiceAccount `
        --set-env-vars "GCP_PROJECT_ID=$ProjectId,BQ_DATASET=$BigQueryDataset,BQ_LOCATION=$BigQueryLocation,LOG_LEVEL=INFO" `
        --allow-unauthenticated `
        --platform managed `
        --quiet
    Assert-Success "Cloud Run deployment failed"

    Show-Step 6 "Fetching Cloud Run URL"
    $ServiceUrl = gcloud run services describe $ServiceName `
        --project $ProjectId `
        --region $Region `
        --format "value(status.url)"
    Assert-Success "Unable to fetch Cloud Run URL"
    if ([string]::IsNullOrWhiteSpace($ServiceUrl)) { throw "Cloud Run URL was empty." }
    Write-Host "Service URL: $ServiceUrl" -ForegroundColor Green

    Show-Step 7 "Triggering the ingestion API"
    $Request = Get-Content $RequestFile -Raw | ConvertFrom-Json
    $Request.bucket = $BucketName
    $TempRequest = Join-Path ([System.IO.Path]::GetTempPath()) "travel-request.json"
    $Request | ConvertTo-Json | Set-Content $TempRequest -Encoding utf8
    curl.exe --fail-with-body -X POST "$ServiceUrl/load" `
        -H "Content-Type: application/json" `
        --data-binary "@$TempRequest"
    Assert-Success "API trigger failed"
    Remove-Item $TempRequest -ErrorAction SilentlyContinue

    Write-Host "`nDeployment and ingestion completed successfully." -ForegroundColor Green
}
finally {
    Pop-Location
}
