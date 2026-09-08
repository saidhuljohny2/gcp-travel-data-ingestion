# Deployment guide

Step-by-step Google Cloud **Console** and **CLI** (PowerShell) instructions to run the travel ingestion API. Replace every `YOUR_*` placeholder. **Do not create or download a service-account key JSON.** Local authentication is ADC; Cloud Run uses an attached service account.

Related: [../README.md](../README.md), [architecture.md](architecture.md).

---

## Placeholders

| Placeholder | Example shape (not real) |
| --- | --- |
| `YOUR_GCP_PROJECT_ID` | GCP project ID |
| `YOUR_BUCKET_NAME` | Globally unique bucket name |
| `YOUR_REGION` | `us-central1` (or your region) |
| `YOUR_CLOUD_RUN_URL` | `https://travel-ingestion-api-…..run.app` |

Suggested names used in scripts: repository `travel-platform`, image `travel-ingestion-api:v1`, service `travel-ingestion-api`, dataset `travel_analytics`, SA `travel-ingestion-sa`.

---

## 1. Project, login, and APIs

### Console

1. Open Google Cloud Console → select or create **YOUR_GCP_PROJECT_ID** (billing on).
2. **APIs & Services → Enable APIs and Services** and enable:
   - Cloud Run Admin API
   - Artifact Registry API
   - Cloud Storage API
   - BigQuery API
   - Identity and Access Management (IAM) API
   - Cloud Build API (optional; used if you later switch to Cloud Build)

> **Screenshot placeholder:** Enabled APIs list (`images/screenshots/enabled-apis.png`).

### CLI (PowerShell)

```powershell
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID
gcloud config set compute/region YOUR_REGION

gcloud services enable `
  run.googleapis.com `
  artifactregistry.googleapis.com `
  storage.googleapis.com `
  bigquery.googleapis.com `
  iam.googleapis.com `
  cloudbuild.googleapis.com
```

---

## 2. Cloud Storage bucket and CSV upload

The API reads **`incoming/employee_travel.csv`** (see `scripts/sample_request.json`).

### Console

1. **Cloud Storage → Buckets → Create**.
2. Name: `YOUR_BUCKET_NAME`. Location type: **Region** or **Multi-region US** (match how you think about BigQuery `US`). Uniform access recommended.
3. Open the bucket → **Upload files** is easier after creating folder `incoming`, or upload and rename/move to `incoming/employee_travel.csv`.
4. Confirm the object exists: `gs://YOUR_BUCKET_NAME/incoming/employee_travel.csv`.

> **Screenshot placeholder:** Object details (`images/screenshots/gcs-object.png`).

### CLI

```powershell
gcloud storage buckets create gs://YOUR_BUCKET_NAME `
  --project=YOUR_GCP_PROJECT_ID `
  --location=US `
  --uniform-bucket-level-access

gcloud storage cp data/employee_travel.csv `
  gs://YOUR_BUCKET_NAME/incoming/employee_travel.csv

gcloud storage ls gs://YOUR_BUCKET_NAME/incoming/
```

Keep the bucket **private**. The runtime SA needs read access via IAM, not allUsers.

---

## 3. BigQuery dataset and tables

### Console

1. **BigQuery → Studio** (or Explorer).
2. Create dataset: ID `travel_analytics`, location **US** (must match `BQ_LOCATION` / `sql/create_dataset.sql`).
3. Run [`sql/create_tables.sql`](../sql/create_tables.sql) in the query editor (project already selected).

Alternatively paste [`sql/create_dataset.sql`](../sql/create_dataset.sql) first if the dataset does not exist.

> **Screenshot placeholder:** Dataset `travel_analytics` with four tables (`images/screenshots/bq-tables.png`).

### CLI

```powershell
bq query --use_legacy_sql=false --project_id=YOUR_GCP_PROJECT_ID `
  (Get-Content .\sql\create_dataset.sql -Raw)

bq query --use_legacy_sql=false --project_id=YOUR_GCP_PROJECT_ID `
  (Get-Content .\sql\create_tables.sql -Raw)

bq ls --project_id=YOUR_GCP_PROJECT_ID travel_analytics
```

macOS/Linux: `bq query --use_legacy_sql=false < sql/create_dataset.sql`.

Confirm tables: `travel_staging`, `employee_travel`, `travel_rejected`, `pipeline_audit`.

---

## 4. Runtime service account and minimum IAM

Create **`travel-ingestion-sa`**. Grant **only** these three project roles for the demo. **Do not** click “Create key” / JSON download.

### Why these three roles

| Role | ID | Why this API needs it |
| --- | --- | --- |
| Storage Object Viewer | `roles/storage.objectViewer` | `blob.download_as_bytes()` on the CSV. Without it: HTTP **403** from GCS. |
| BigQuery Data Editor | `roles/bigquery.dataEditor` | Load jobs into staging/rejected, `insert_rows_json` on audit, `MERGE` updates/inserts on `employee_travel`. Viewer is not enough. |
| BigQuery Job User | `roles/bigquery.jobUser` | Permission to **run** load and query jobs in the project. Data Editor without Job User typically fails job creation. |

These are **data-plane** roles for the Cloud Run identity. Your **user** still needs broader **control-plane** roles to deploy (enable APIs, create SA, push images, `run.admin`, `iam.serviceAccountUser` on this SA).

### Console

1. **IAM & Admin → Service Accounts → Create**.
2. Name: `travel-ingestion-sa`.
3. **IAM & Admin → IAM → Grant access** (or the SA’s **Permissions** tab):
   - Principal: `travel-ingestion-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com`
   - Roles: Storage Object Viewer, BigQuery Data Editor, BigQuery Job User.
4. Skip **Keys**.

> **Screenshot placeholder:** SA principals and three roles (`images/screenshots/iam-sa.png`).

### CLI

```powershell
gcloud iam service-accounts create travel-ingestion-sa `
  --project=YOUR_GCP_PROJECT_ID `
  --display-name="Travel ingestion Cloud Run SA"

$Sa = "serviceAccount:travel-ingestion-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID `
  --member=$Sa --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID `
  --member=$Sa --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID `
  --member=$Sa --role="roles/bigquery.jobUser"
```

For **local** Flask/Docker, run `gcloud auth application-default login` and grant **your user** the same three roles (or Owner on a sandbox). Still no JSON key.

---

## 5. Local ADC (optional before Docker/Cloud Run)

```powershell
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID

$env:GCP_PROJECT_ID = "YOUR_GCP_PROJECT_ID"
$env:GOOGLE_CLOUD_PROJECT = "YOUR_GCP_PROJECT_ID"
$env:BQ_DATASET = "travel_analytics"
$env:BQ_LOCATION = "US"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

```powershell
curl.exe http://localhost:8080/
```

Edit `scripts/sample_request.json` (`bucket`: `YOUR_BUCKET_NAME`) then:

```powershell
curl.exe -X POST http://localhost:8080/load `
  -H "Content-Type: application/json" `
  --data-binary "@scripts/sample_request.json"
```

---

## 6. Artifact Registry: create, build, tag, push

### Console

1. **Artifact Registry → Repositories → Create**.
2. Format: **Docker**. Name: `travel-platform`. Location: `YOUR_REGION`.
3. You still build/push from the CLI (or Cloud Build). Console is for verifying the image after push.

> **Screenshot placeholder:** Repository created (`images/screenshots/artifact-registry-repo.png`).

### CLI

```powershell
gcloud artifacts repositories create travel-platform `
  --repository-format=docker `
  --location=YOUR_REGION `
  --project=YOUR_GCP_PROJECT_ID `
  --description="Travel ingestion images"

gcloud auth configure-docker "YOUR_REGION-docker.pkg.dev"

docker build -t travel-ingestion-api:v1 .

docker tag travel-ingestion-api:v1 `
  "YOUR_REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/travel-platform/travel-ingestion-api:v1"

docker push `
  "YOUR_REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/travel-platform/travel-ingestion-api:v1"
```

> **Screenshot placeholder:** Image tag `v1` in the repository (`images/screenshots/artifact-registry.png`).

Your user needs Artifact Registry **Writer** (or equivalent) on the repo/project.

---

## 7. Cloud Run deploy

### Console

1. **Cloud Run → Deploy container → Service**.
2. Container image: the Artifact Registry URL from the previous step.
3. Service name: `travel-ingestion-api`. Region: `YOUR_REGION`.
4. **Authentication:** Allow unauthenticated invocations — **demo only**. Production: Require authentication.
5. **Container, variables & secrets, connections, security:**
   - Service account: `travel-ingestion-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com`
   - Environment variables:
     - `GCP_PROJECT_ID` = `YOUR_GCP_PROJECT_ID`
     - `BQ_DATASET` = `travel_analytics`
     - `BQ_LOCATION` = `US`
     - `LOG_LEVEL` = `INFO`
   - Container port: `8080` (matches `EXPOSE` / gunicorn).
6. Deploy. Copy the **https** URL → `YOUR_CLOUD_RUN_URL`.

> **Screenshot placeholder:** Service overview (URL, SA, env) (`images/screenshots/cloud-run-service.png`).

### CLI

```powershell
gcloud run deploy travel-ingestion-api `
  --project YOUR_GCP_PROJECT_ID `
  --region YOUR_REGION `
  --image "YOUR_REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/travel-platform/travel-ingestion-api:v1" `
  --service-account "travel-ingestion-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com" `
  --set-env-vars "GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID,BQ_DATASET=travel_analytics,BQ_LOCATION=US,LOG_LEVEL=INFO" `
  --allow-unauthenticated `
  --platform managed

gcloud run services describe travel-ingestion-api `
  --project YOUR_GCP_PROJECT_ID `
  --region YOUR_REGION `
  --format "value(status.url)"
```

`--allow-unauthenticated` is for the Udemy/GitHub demo so `curl.exe` works without an identity token. It grants `allUsers` **Cloud Run Invoker**. Do not use this pattern for confidential travel data.

Automated path: set `ProjectId` and `BucketName` in `scripts/deploy.ps1`, then `.\scripts\deploy.ps1`.

---

## 8. Deployment verification

### Health

```powershell
curl.exe "YOUR_CLOUD_RUN_URL/"
```

Expect HTTP 200 and `"status":"UP"`.

### Trigger load (exact curl.exe)

```powershell
curl.exe -X POST "YOUR_CLOUD_RUN_URL/load" `
  -H "Content-Type: application/json" `
  --data-binary "@scripts/sample_request.json"
```

Expect `"status":"SUCCESS"`, `records_read` ≈ 1000, `records_loaded` ≈ 965, `records_rejected` ≈ 35.

> **Screenshot placeholder:** Terminal SUCCESS JSON (`images/screenshots/curl-success.png`).

### Audit API

```powershell
curl.exe "YOUR_CLOUD_RUN_URL/audit?limit=5"
```

Or `.\scripts\test_api.ps1 -ServiceUrl "YOUR_CLOUD_RUN_URL"`.

### BigQuery

In Console, run queries from [`sql/validation_queries.sql`](../sql/validation_queries.sql):

- `COUNT(*)` on `employee_travel` ≈ 965 after first successful load.
- Duplicate `booking_id` query returns **no rows**.
- `travel_rejected` grouped by `rejection_reason`.
- `pipeline_audit` latest row `SUCCESS` with matching `execution_id`.

> **Screenshot placeholder:** Query results (`images/screenshots/bq-validation.png`).

### Logs

**Cloud Run → service → Logs** (or Logs Explorer). Filter on `execution_id=` from the JSON response.

> **Screenshot placeholder:** Log line with `Pipeline success` (`images/screenshots/cloud-logging.png`).

### Idempotency check

Run the same `curl.exe` `POST /load` again. Final table count should stay ~965; a new audit row appears; rejected row count **increases** (append-only).

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Cloud Run deploy: cannot act as SA | Missing `roles/iam.serviceAccountUser` on `travel-ingestion-sa` for your user | Grant Service Account User on that SA |
| Image pull/push denied | Wrong `configure-docker` host or no AR Writer | `gcloud auth configure-docker YOUR_REGION-docker.pkg.dev` |
| 403 on `/load` | Runtime SA missing Object Viewer / BQ roles | Re-apply the three roles; wait a minute for IAM |
| 404 on `/load` | Wrong bucket/object in JSON | `gcloud storage ls gs://YOUR_BUCKET_NAME/incoming/` |
| 500 dataset/table not found | SQL not applied or wrong `BQ_DATASET` / project env | Re-run create SQL; check Cloud Run env vars |
| Health OK, load fails | Health does not use GCP | Check logs; confirm SA and tables |
| PowerShell `curl` returns unexpected object | `curl` alias is `Invoke-WebRequest` | Always `curl.exe` |
| Local Docker 401/ADC errors | ADC not mounted | Mount `%APPDATA%\gcloud` to `/adc` and set `GOOGLE_APPLICATION_CREDENTIALS` to the **ADC** file, not an SA key |
| Unauthenticated 403 on Cloud Run | Deployed with required auth | Demo: `--allow-unauthenticated`; else identity token |

---

## 10. Cleanup

Console: delete the Cloud Run service, Artifact Registry repository, GCS bucket, BigQuery dataset, and the service account (IAM).

CLI:

```powershell
gcloud run services delete travel-ingestion-api `
  --region YOUR_REGION --project YOUR_GCP_PROJECT_ID --quiet

gcloud artifacts repositories delete travel-platform `
  --location YOUR_REGION --project YOUR_GCP_PROJECT_ID --quiet

gcloud storage rm -r gs://YOUR_BUCKET_NAME

bq rm -r -f -d YOUR_GCP_PROJECT_ID:travel_analytics

gcloud iam service-accounts delete `
  travel-ingestion-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com `
  --project YOUR_GCP_PROJECT_ID --quiet
```

Leave APIs enabled or disable them if the project is a throwaway sandbox.
