# Teacher Guide — GCP Travel Data Ingestion Platform

Use this document to **explain and execute** the project live in class (Udemy, corporate batch, or GitHub walkthrough). Each lesson has:

- **Say** — talking points (keep these on screen or as speaker notes)
- **Show** — files or Console screens to open
- **Do** — commands you run with students
- **Check** — proof the step worked
- **Ask** — one question to lock the concept

Suggested total runtime: **3.5 to 4.5 hours** (can split across two sessions).

Related materials: [../README.md](../README.md), [architecture.md](architecture.md), [deployment-guide.md](deployment-guide.md).

---

## How to teach this project

Teach in this order. Do **not** start by scrolling the whole repo.

1. Business problem (why this exists)
2. Architecture (two flows: data and deploy)
3. Dataset and quality rules (why 35 rows fail)
4. Code walk (one module per pipeline step)
5. GCP setup (bucket, BigQuery, IAM)
6. Deploy Cloud Run
7. Trigger API and prove BigQuery results
8. Replay the same file (idempotency)
9. Failures, logs, audit
10. Interview recap

**Classroom rules**

- Never create a service-account JSON key.
- Replace `YOUR_*` placeholders. Do not commit real project IDs.
- Unauthenticated Cloud Run is **demo only**. Say that every time you deploy `--allow-unauthenticated`.
- If a student hits a 403, stop and teach IAM before retrying blindly.

**Two teaching modes**

| Mode | When | What you do |
| --- | --- | --- |
| Full lab | Students have their own GCP project + billing | Everyone runs the **Do** blocks |
| Instructor demo | One shared project | You execute; students follow architecture + code |

This repo was already deployed once to `gcp-evening-batch-501811` for instructor verification. Use that only if you own the project. Students should use **their** project.

---

## Session map

| # | Lesson | Time | Outcome |
| --- | --- | --- | --- |
| 0 | Prerequisites and login | 15 min | `gcloud` project selected |
| 1 | Business + architecture | 25 min | Students can draw GCS → Cloud Run → BigQuery |
| 2 | Dataset and validation rules | 20 min | They can name the 7 reject reasons |
| 3 | Code walkthrough | 45 min | They can narrate `POST /load` |
| 4 | SQL and BigQuery design | 25 min | Four tables and MERGE explained |
| 5 | GCP setup lab | 30 min | Bucket, CSV, dataset, SA exist |
| 6 | Build and deploy | 35 min | Cloud Run URL is live |
| 7 | Execute and verify | 25 min | 965 / 35 / audit row |
| 8 | Idempotency lab | 15 min | Count stays 965 on replay |
| 9 | Errors, logs, IAM recap | 20 min | 400/403/404/422 mapped |
| 10 | Interview drill | 20 min | 15 questions from README |

---

## Lesson 0 — Prerequisites and login

**Say.** We will use Application Default Credentials on the laptop and a dedicated Cloud Run service account in GCP. Logging into the Console in a browser is not the same as authenticating the CLI.

**Show.** Terminal + [Google Cloud Console](https://console.cloud.google.com).

**Do.**

```bash
gcloud auth login --update-adc
gcloud config set project YOUR_GCP_PROJECT_ID
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
gcloud config get-value project
gcloud auth list
```

Enable APIs (one time per project):

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  iam.googleapis.com \
  cloudbuild.googleapis.com
```

**Check.** `gcloud config get-value project` prints the student project. Billing is on.

**Ask.** Why is Console login not enough to run this API from your laptop?  
*Answer: Python client libraries use ADC, not the browser cookie.*

**Teacher trap.** `gcloud` missing or Docker missing is fine for the source deploy path (`gcloud run deploy --source .` uses Cloud Build). Local Docker is optional.

---

## Lesson 1 — Business problem and architecture

**Say.**

- A company drops a daily CSV into GCS `incoming/`.
- Analytics needs **clean** bookings in BigQuery, not raw garbage.
- Engineering exposes a REST API on Cloud Run so any scheduler (`curl`, Cloud Scheduler, a notebook) can trigger a load.
- Re-running yesterday’s file must **not** duplicate `booking_id`.

**Show.** `images/architecture.png` then the Mermaid diagrams in `docs/architecture.md`.

Draw two arrows on a whiteboard:

```text
Deploy:  Git → Docker → Artifact Registry → Cloud Run
Data:    GCS CSV → Cloud Run (validate/transform) → BigQuery
```

**Say the four BigQuery tables out loud.**

| Table | Audience | Behavior |
| --- | --- | --- |
| `travel_staging` | Engineers | Append valid rows for this run |
| `employee_travel` | Analysts | Current truth; MERGE on `booking_id` |
| `travel_rejected` | Data owners | Bad rows + reason |
| `pipeline_audit` | Ops | One row per API execution |

**Do.** Open `README.md` project overview table. Do not deploy yet.

**Check.** A student can point to where rejected rows go vs where dashboards should read.

**Ask.** Why not load the CSV straight into BigQuery with autodetect?  
*Answer: No validation reasons, no transform, duplicates on replay, no HTTP audit contract.*

---

## Lesson 2 — Dataset and data quality

**Say.** Production files are messy. This sample is **designed** to fail some rows so the reject table is not theoretical.

**Show.** `data/employee_travel.csv` in a spreadsheet or `head`/`tail`.

**Do.**

```bash
wc -l data/employee_travel.csv
# 1001 = header + 1000 rows
```

Walk the rules in `src/validator.py` (`REQUIRED_COLUMNS`, `VALID_STATUSES`):

| Rule | Reject message |
| --- | --- |
| Missing `booking_id` / `employee_id` / `employee_name` | `… is missing` |
| Duplicate `booking_id` in the **same file** (keep first) | `duplicate booking_id in source file` |
| Price missing, non-numeric, or `≤ 0` | `ticket_price must be greater than zero` |
| Unparseable dates | `travel_date` / `return_date` is invalid |
| Return before travel | `return_date is earlier than travel_date` |
| Status not CONFIRMED / PENDING / CANCELLED | `booking_status is invalid` |

**Say what is NOT a reject.** Extra spaces, `london`, `confirmed`, `usd` — those are **transformed**, not rejected.

**Expected counts for the shipped CSV:** 965 valid, 35 rejected.

**Check.** Students find one bad date (`2026-99-42`) and one padded name.

**Ask.** If we title-cased names before validating, what would go wrong?  
*Answer: Blank names might look “filled”; invalid dates might still compute duration incorrectly.*

---

## Lesson 3 — Code walkthrough (`POST /load`)

Open files **in pipeline order**. Pause after each file. Do not read every line.

### 3.1 API contract — `app.py`

**Say.** Flask is the HTTP façade. Business logic lives in `src/`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Health; **no GCP calls** (good liveness probe) |
| `GET` | `/audit` | Latest `pipeline_audit` rows |
| `POST` | `/load` | Full ETL |

**Show** the JSON body:

```json
{
  "bucket": "YOUR_BUCKET_NAME",
  "file": "incoming/employee_travel.csv"
}
```

**Say** the success envelope: `status`, `execution_id`, `records_read`, `records_loaded`, `records_rejected`, `processing_time`.

Walk `load()` in `app.py` as a numbered list (write this on the board):

1. UUID `execution_id`
2. Validate JSON (`bucket`, `file`, must end with `.csv`)
3. Read GCS
4. Validate → split frames
5. Transform valid + rejected
6. Staging load → MERGE → rejected load
7. Audit SUCCESS
8. On exception: HTTP status + audit FAILED

**Ask.** Why generate `execution_id` before GCS?  
*Answer: Logs and failure audits can still correlate the attempt.*

### 3.2 Config — `src/config.py`

**Say.** No hardcoded project IDs. `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT`, plus `BQ_DATASET`, `BQ_LOCATION`, `PORT`, `LOG_LEVEL`.

### 3.3 GCS — `src/gcs_reader.py`

**Say.** Read as **strings** (`dtype=str`, NA filter off) so blanks stay blanks. Map `NotFound` → 404, `Forbidden` → 403, empty/parse → 422.

### 3.4 Validate — `src/validator.py`

**Say.** Collect **all** reasons per row (semicolon joined). Schema missing columns fails the **whole** job.

### 3.5 Transform — `src/transformer.py`

**Say.**

- Trim every string
- Title case: `employee_name`, cities
- Upper: `booking_status`, `currency`
- `travel_duration_days` = return − travel
- Lineage: `processed_at`, `source_file`, `execution_id`

**Ask.** Why keep rejected dates as strings in BigQuery?  
*Answer: Invalid values like `2026-99-42` cannot be DATE; quarantine must preserve the original.*

### 3.6 BigQuery + audit — `src/bigquery_loader.py`, `src/audit.py`

**Say.** Staging is append. MERGE is the only writer of current facts. Audit is `insert_rows_json` (one row).

### 3.7 Logging — `src/logger.py`

**Say.** Stdout goes to Cloud Logging. Every `/load` line carries `execution_id=`.

**Check.** A student can recap the seven steps without looking at `app.py`.

---

## Lesson 4 — SQL and warehouse design

**Show.** `sql/create_dataset.sql`, `sql/create_tables.sql`, `sql/merge_employee_travel.sql`.

**Say.**

- Dataset `travel_analytics`, location **US** (must match `BQ_LOCATION`).
- Staging partitioned by `DATE(processed_at)` with **30-day** expiry — cheap debug, auto-cleanup.
- Final table partitioned by `travel_date`, clustered by `department`, `booking_status`, `booking_id`.
- `ticket_price` is **FLOAT64** so pandas `load_table_from_dataframe` works. NUMERIC + Python `Decimal`/`float64` is a common production foot-gun (pyarrow byte length errors). Mention this as a war story.

**MERGE talking script (read slowly):**

1. USING only staging rows for **this** `@execution_id`
2. `ROW_NUMBER()` so the MERGE source has one row per `booking_id`
3. `ON booking_id`
4. MATCHED → UPDATE all non-key columns (including lineage)
5. NOT MATCHED → INSERT

**Ask.** Does MERGE make HTTP exactly-once?  
*Answer: No. It makes the **fact table** converge on the latest valid booking. Rejected and audit tables still append.*

---

## Lesson 5 — GCP setup lab (execute)

Students work in **their** project. Instructor screenshares Console + CLI.

### 5.1 Bucket and CSV

**Do.**

```bash
export PROJECT_ID="YOUR_GCP_PROJECT_ID"
export BUCKET="travel-incoming-${PROJECT_ID}"   # must be globally unique
export REGION="us-central1"

gcloud storage buckets create "gs://${BUCKET}" \
  --project="${PROJECT_ID}" \
  --location=US \
  --uniform-bucket-level-access

gcloud storage cp data/employee_travel.csv \
  "gs://${BUCKET}/incoming/employee_travel.csv"

gcloud storage ls "gs://${BUCKET}/incoming/"
```

**Check.** Object exists. Bucket is **not** public.

**Show.** Console → Cloud Storage → object details.

### 5.2 BigQuery tables

**Do.**

```bash
bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" < sql/create_dataset.sql
bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" < sql/create_tables.sql
bq ls --project_id="${PROJECT_ID}" travel_analytics
```

**Check.** Four tables listed.

### 5.3 Runtime service account (no keys)

**Say each role once.**

| Role | Why |
| --- | --- |
| `roles/storage.objectViewer` | Download the CSV |
| `roles/bigquery.dataEditor` | Load / MERGE / audit insert |
| `roles/bigquery.jobUser` | Create BigQuery jobs |

**Do.**

```bash
gcloud iam service-accounts create travel-ingestion-sa \
  --project="${PROJECT_ID}" \
  --display-name="Travel ingestion Cloud Run SA"

export SA_EMAIL="travel-ingestion-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectViewer"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.jobUser"

# Deployer must be allowed to attach this SA to Cloud Run
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project "${PROJECT_ID}" \
  --member="user:YOUR_LOGIN_EMAIL" \
  --role="roles/iam.serviceAccountUser"
```

**Ask.** Why Job User *and* Data Editor?  
*Answer: Data Editor lets you change table data; Job User lets you **run** the load/query job.*

**Check.** IAM bindings visible in Console. **Keys tab is empty.**

---

## Lesson 6 — Build and deploy (execute)

**Say.** Image is built from `Dockerfile` (Python 3.11 slim, gunicorn, `PORT`). Cloud Build can build if Docker is not on the laptop.

### Path A — Cloud Build (recommended in class)

**Do.** From the repo root:

```bash
gcloud run deploy travel-ingestion-api \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --service-account "${SA_EMAIL}" \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},BQ_DATASET=travel_analytics,BQ_LOCATION=US,LOG_LEVEL=INFO" \
  --allow-unauthenticated \
  --timeout 300
```

Takes several minutes the first time (Artifact Registry repo + build).

### Path B — Local Docker + Artifact Registry

Follow `docs/deployment-guide.md` sections 6–7, or `scripts/deploy.ps1` on Windows after editing `ProjectId` and `BucketName`.

**Check.**

```bash
gcloud run services describe travel-ingestion-api \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format "value(status.url)"
```

```bash
curl -sS "YOUR_CLOUD_RUN_URL/"
```

Expect `"status":"UP"`.

**Show.** Cloud Run → Revisions → environment variables and service account.

**Ask.** Why inject `GCP_PROJECT_ID` instead of baking it into the image?  
*Answer: Same image can be promoted across projects/envs.*

---

## Lesson 7 — Execute the pipeline and verify (execute)

**Do.** Edit `scripts/sample_request.json` or inline JSON:

```bash
export URL="YOUR_CLOUD_RUN_URL"
export BUCKET="travel-incoming-YOUR_GCP_PROJECT_ID"

curl -sS -X POST "${URL}/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"${BUCKET}\",\"file\":\"incoming/employee_travel.csv\"}"
```

**Expected JSON.**

```json
{
  "status": "SUCCESS",
  "execution_id": "…",
  "records_read": 1000,
  "records_loaded": 965,
  "records_rejected": 35,
  "processing_time": "…"
}
```

**Do.** Audit API:

```bash
curl -sS "${URL}/audit?limit=5"
```

**Do.** BigQuery — run `sql/validation_queries.sql` in Console, or:

```bash
bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" '
SELECT COUNT(*) AS total_loaded FROM `travel_analytics.employee_travel`'

bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" '
SELECT booking_id, COUNT(*) AS occurrences
FROM `travel_analytics.employee_travel`
GROUP BY booking_id HAVING COUNT(*) > 1'

bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" '
SELECT rejection_reason, COUNT(*) AS rejected_count
FROM `travel_analytics.travel_rejected`
GROUP BY rejection_reason ORDER BY rejected_count DESC'

bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" '
SELECT execution_id, status, records_read, records_loaded, records_rejected
FROM `travel_analytics.pipeline_audit`
ORDER BY start_time DESC
LIMIT 5'
```

**Show.** Logs Explorer: filter `execution_id=` from the JSON. Point at `Pipeline success`.

**Check.** Final count 965; duplicate query empty; seven reject reasons (~5 rows each on first success); sample names are title case.

**Live demo script (narrate while queries run):**

1. “Analysts only query `employee_travel`.”
2. “Ops prove the run in `pipeline_audit`.”
3. “Data stewards fix files using `travel_rejected`.”

---

## Lesson 8 — Idempotency lab (execute)

**Do.** Run the **same** `POST /load` again.

**Say what you expect before you run it.** Write this on the board:

| Surface | After 2nd SUCCESS |
| --- | --- |
| `employee_travel` COUNT | Still **965** |
| Duplicate `booking_id` | Still **zero** |
| `travel_rejected` | **+35** rows (append) |
| `pipeline_audit` | **+1** SUCCESS row |
| `travel_staging` | **+965** rows for the new `execution_id` |

**Check.** Counts match the table. Lineage columns `execution_id` / `processed_at` on a sample booking **changed** (UPDATE path of MERGE).

**Ask.** How would we make rejected rows idempotent too?  
*Discussion: hash of (file, booking_id, reason) or MERGE into rejected; we kept append-on-purpose for an operational history.*

---

## Lesson 9 — Failures, HTTP codes, IAM

**Do live (optional, fast):**

```bash
# 400 — missing bucket
curl -sS -X POST "${URL}/load" -H "Content-Type: application/json" -d '{"file":"incoming/employee_travel.csv"}'

# 404 — wrong object
curl -sS -X POST "${URL}/load" -H "Content-Type: application/json" \
  -d "{\"bucket\":\"${BUCKET}\",\"file\":\"incoming/does-not-exist.csv\"}"
```

**Say the map.**

| HTTP | Typical cause |
| --- | --- |
| 400 | Bad JSON, empty `bucket`/`file`, not `.csv` |
| 403 | Runtime SA missing Object Viewer / BQ roles |
| 404 | Object missing |
| 422 | Empty CSV or missing columns |
| 500 | Tables missing, unexpected bug |

**Show.** `pipeline_audit` FAILED rows from earlier experiments (error_message truncated to 1024 chars).

**IAM recap (board).**

```text
Your user     = control plane (deploy, enable APIs, attach SA)
Cloud Run SA  = data plane (read GCS, write BQ)
ADC locally   = your user acting as data plane for laptop tests
JSON keys     = not used
```

---

## Lesson 10 — Interview drill (15 minutes)

Use the 15 Q&A in [../README.md](../README.md#interview-questions-15). Suggested live order:

1. Cloud Run vs load job vs Dataflow  
2. No JSON keys / ADC vs attached SA  
3. Three IAM roles  
4. Validate before transform  
5. MERGE + `execution_id` + `ROW_NUMBER`  
6. Why staging exists  
7. Why quarantine instead of failing the file  
8. Audit table purpose  
9. Partition / cluster choices  
10. `--allow-unauthenticated` vs identity token  

Have one student answer; you correct with the README wording.

---

## Suggested slide / section titles (Udemy)

1. The travel-booking problem  
2. Target architecture  
3. Folder tour (60 seconds)  
4. Dirty CSV on purpose  
5. Flask API contract  
6. Python ETL modules  
7. BigQuery tables and MERGE  
8. IAM without key files  
9. Deploy to Cloud Run  
10. First load — 965 and 35  
11. Second load — still 965  
12. Logs and audit  
13. Break it (400/404)  
14. Interview pack  
15. Cleanup  

---

## Folder tour script (60 seconds)

Open the tree and say one sentence per path:

| Path | Sentence |
| --- | --- |
| `app.py` | HTTP API |
| `src/` | ETL steps |
| `sql/` | Warehouse DDL + MERGE + validation queries |
| `data/employee_travel.csv` | Upload this; not baked into Docker |
| `Dockerfile` | What Cloud Run runs |
| `scripts/deploy.ps1` | Windows one-click deploy |
| `docs/` | Architecture, deploy, this teacher guide |

---

## Timing if you only have 90 minutes

1. Architecture + dataset (15)  
2. Code: `app.py` + validator + MERGE SQL (25)  
3. Deploy `--source` if APIs already enabled (25)  
4. Load twice + three BigQuery queries (15)  
5. IAM + interview (10)  

Skip local Flask/Docker unless someone asks.

---

## Common student failures (fix in class)

| Symptom | Fix |
| --- | --- |
| Health OK, load 403 | Grant the three roles to **runtime SA**, wait ~1 min |
| Load 500 dataset/table not found | Re-run `sql/create_*.sql`; check `BQ_DATASET` env |
| Deploy cannot act as SA | `roles/iam.serviceAccountUser` on the SA for the **user** |
| PowerShell `curl` returns an object | Use `curl.exe` |
| `ticket_price` pyarrow / “bytestring length 8” | Keep FLOAT64 schema + float64 pandas (already in this repo) |
| Second load “duplicates reports” | They counted `travel_rejected` or staging, not `employee_travel` |

---

## Cleanup (end of workshop)

```bash
gcloud run services delete travel-ingestion-api --region "${REGION}" --project "${PROJECT_ID}" --quiet
gcloud storage rm -r "gs://${BUCKET}"
bq rm -r -f -d "${PROJECT_ID}:travel_analytics"
gcloud iam service-accounts delete "${SA_EMAIL}" --project "${PROJECT_ID}" --quiet
```

Leave Artifact Registry unless you want to delete the `cloud-run-source-deploy` (or `travel-platform`) repository too.

---

## Instructor checklist (print this)

- [ ] Billing on, APIs enabled  
- [ ] CSV in `incoming/`  
- [ ] Four BigQuery tables  
- [ ] Runtime SA, no JSON key  
- [ ] Cloud Run env vars set  
- [ ] First load 965 / 35  
- [ ] Second load still 965  
- [ ] Duplicate query empty  
- [ ] Logs show `execution_id`  
- [ ] Said “demo unauthenticated” out loud  
- [ ] Cleanup or warn about cost  

---

## Homework / portfolio assignment

Students submit a short write-up:

1. Screenshot of SUCCESS JSON  
2. Screenshot of `employee_travel` count = 965  
3. Screenshot of duplicate query = 0 rows  
4. One paragraph: how MERGE prevented duplicates  
5. One paragraph: three IAM roles and why  

Optional stretch: Cloud Scheduler HTTP target to `POST /load` on a cron (still no JSON keys; use OIDC if they lock down the service).
