# Teacher Guide (Console Edition) — GCP Travel Data Ingestion Platform

Run the **entire project from the Google Cloud Console** in front of students. This guide tells you **where to click**, **what to type**, **what to point at**, and **what to say**.

Each lesson has:

- **Say** — talking points
- **Click** — exact Console navigation
- **Type** — values to enter (replace `YOUR_*` unless you are using the instructor demo project)
- **Point at** — what to highlight on screen
- **Check** — proof it worked
- **Ask** — one question to lock the concept

Related: [../README.md](../README.md), [architecture.md](architecture.md), [codebase-guide.md](codebase-guide.md), [deployment-guide.md](deployment-guide.md), [ci-cd.md](ci-cd.md).

> **Placeholders (student labs)**
> - `YOUR_PROJECT_ID` — student GCP project
> - `YOUR_BUCKET` — globally unique, suggest `travel-incoming-YOUR_PROJECT_ID`
> - `YOUR_REGION` — `us-central1`
> - `YOUR_CLOUD_RUN_URL` — appears after deploy, ends `.run.app`
>
> **Say every deploy:** "Unauthenticated access is a classroom demo only. In production we require an identity token." **Never create a service-account JSON key.**

---

## Instructor live demo (already built)

Use this when you are teaching from the verified project instead of building from zero. Students still follow the Click path on their own projects.

| Item | Value |
| --- | --- |
| Project | `gcp-evening-batch-501811` |
| GitHub | https://github.com/saidhuljohny2/gcp-travel-data-ingestion |
| Cloud Run | https://travel-ingestion-api-l4mjv2qmxq-uc.a.run.app |
| Bucket | `travel-incoming-gcp-evening-batch-501811` |
| Incoming objects | `employee_travel_20260907.csv`, `_20260908.csv`, `_20260909.csv` |
| Dataset | `travel_analytics` |
| Runtime SA | `travel-ingestion-sa@gcp-evening-batch-501811.iam.gserviceaccount.com` |
| Image repo | `us-central1-docker.pkg.dev/gcp-evening-batch-501811/travel-platform/travel-ingestion-api` |
| Verified `/load` (day 20260907) | 300 read, **286 loaded**, **14 rejected** |

**Live trigger (Cloud Shell):**

```bash
URL="https://travel-ingestion-api-l4mjv2qmxq-uc.a.run.app"
BUCKET="travel-incoming-gcp-evening-batch-501811"

curl -s -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"$BUCKET\",\"file\":\"incoming/employee_travel_20260907.csv\"}"
```

**Redeploy without a GitHub trigger** (already proven):

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_IMAGE_TAG=$(git rev-parse --short HEAD)
```

---

## Before class — instructor prep (do NOT do live)

Cloud Build container builds take **3–8 minutes**. Pre-warm so class does not stall.

- Billing on. Repo cloned locally so you can drag files from `data/incoming/`.
- Optional: keep the instructor project above already deployed so Lesson 7–10 can run even if a student deploy is still building.
- Open these Console tabs:
  1. **APIs & Services**
  2. **Cloud Storage → Buckets**
  3. **BigQuery → Studio**
  4. **IAM & Admin → Service Accounts**
  5. **Cloud Run**
  6. **Artifact Registry**
  7. **Cloud Build → History / Triggers**
  8. **Logging → Logs Explorer**

**One-time truth to teach:** six Console areas — **Storage, BigQuery, IAM, Cloud Run, Artifact Registry, Cloud Build**. Draw those boxes first. Logging is how you prove a run.

---

## Session map (Console demo)

| # | Lesson | Console area | Time |
| --- | --- | --- | --- |
| 0 | Pick project, enable APIs | APIs & Services | 10 min |
| 1 | Business + architecture | slides / whiteboard | 20 min |
| 2 | Bucket + timestamped daily CSVs | Cloud Storage | 15 min |
| 3 | Dirty data walkthrough | Cloud Storage | 15 min |
| 4 | Dataset + 4 tables | BigQuery Studio | 25 min |
| 5 | Runtime service account + roles | IAM & Admin | 20 min |
| 6 | First (manual) deploy | Cloud Run / Cloud Shell | 30 min |
| 7 | Health check | browser | 5 min |
| 8 | Trigger `/load` for one day | Cloud Shell | 15 min |
| 9 | Verify results | BigQuery Studio | 20 min |
| 10 | Replay = idempotency | Cloud Run + BigQuery | 15 min |
| 11 | Logs + audit | Logs Explorer | 15 min |
| 12 | Break it on purpose | Cloud Shell | 10 min |
| 13 | Automate deployment (CI/CD) | Cloud Build | 25 min |
| 14 | Interview recap + cleanup | all areas | 20 min |

Total ≈ 4–4.5 hours. 90-minute path is at the end.

---

## Lesson 0 — Project and APIs (Console)

**Say.** Everything we build lives inside one project. First we turn on the Google services we need.

**Click.** Top blue bar → **project picker** → select `YOUR_PROJECT_ID`.

**Click.** ☰ → **APIs & Services → Enabled APIs & services → + Enable APIs and Services**.

**Enable** (search each, click **Enable**):

- Cloud Run Admin API
- Artifact Registry API
- Cloud Build API
- Cloud Storage
- BigQuery API
- Identity and Access Management (IAM) API

**Point at.** Green checkmarks on the Enabled APIs list.

**Check.** All six show as enabled.

**Ask.** Why must we enable APIs before using a service?  
*Answer: GCP disables most APIs by default for security and billing control.*

> Screenshot: `images/screenshots/enabled-apis.png`

---

## Lesson 1 — Business problem and architecture

**Say.**

- A company drops a **daily** CSV into Cloud Storage `incoming/`.
- File names are dated: `employee_travel_YYYYMMDD.csv` — one object per business day.
- Analysts need **clean** bookings in BigQuery, not raw garbage.
- Engineering exposes a REST API on **Cloud Run** so anything can trigger a load.
- Re-running the **same day's** file must **not** duplicate `booking_id`.
- Loading **day 2** after day 1 **should** add new bookings (different IDs).

**Point at.** `images/architecture.png`, then whiteboard two arrows:

```text
Deploy:  Git → Docker → Artifact Registry → Cloud Run
Data:    GCS incoming/employee_travel_YYYYMMDD.csv → Cloud Run → BigQuery
```

**Say the four tables:**

| Table | Audience | Behavior |
| --- | --- | --- |
| `travel_staging` | Engineers | Append this run's valid rows |
| `employee_travel` | Analysts | Current truth; MERGE on `booking_id` |
| `travel_rejected` | Data owners | Bad rows + reason |
| `pipeline_audit` | Ops | One row per run (`file_name` = the dated path) |

**Ask.** Why not overwrite one file named `employee_travel.csv` every day?  
*Answer: You lose history. Dated names + `pipeline_audit.file_name` prove which day loaded.*

---

## Lesson 2 — Create the bucket and upload timestamped CSVs (Console)

**Say.** This bucket is the landing zone. Production drops **one dated file per day**.

### Create the bucket

**Click.** ☰ → **Cloud Storage → Buckets → + Create**.

**Type.**
- Name: `YOUR_BUCKET` (must be globally unique)
- Location type: **Multi-region**, `US` (match BigQuery `US`)
- Leave **Uniform** access control
- **Create**. Keep public access prevention **on**.

**Point at.** Uniform access — "IAM decides who reads, not per-object ACLs."

### Create `incoming/` and upload three days

**Click.** Open the bucket → **Create folder** → `incoming` → **Create**.

**Click.** Open `incoming` → **Upload files** → select all three from the repo's `data/incoming/`:

| Local file | GCS object | Rows | Expected valid / rejected |
| --- | --- | --- | --- |
| `employee_travel_20260907.csv` | `incoming/employee_travel_20260907.csv` | 300 | **286 / 14** |
| `employee_travel_20260908.csv` | `incoming/employee_travel_20260908.csv` | 300 | **286 / 14** |
| `employee_travel_20260909.csv` | `incoming/employee_travel_20260909.csv` | 300 | **286 / 14** |

Booking ID ranges are **different per day**, so loading all three days accumulates ~**858** clean rows.

**Point at.** The dated object names. Say: "The API does not care about the date format — we pass `file` in JSON. The date is for humans and for audit."

**Check.** Three objects listed under `incoming/`.

**Ask.** Why keep the bucket private if the API needs the file?  
*Answer: The Cloud Run service account gets read access via IAM. We never make travel data public.*

> Need more days? `python scripts/generate_sample_data.py --dates 20260910 --rows 300` then upload.

> If drag-and-drop is blocked, Cloud Shell:  
> `gcloud storage cp data/incoming/*.csv gs://YOUR_BUCKET/incoming/`

> Screenshot: `images/screenshots/gcs-object.png`

---

## Lesson 3 — Look at the dirty data (Console)

**Say.** Real files are messy. Each daily sample is **designed** to fail ~14 rows so the reject table is not empty.

**Click.** In the bucket, click `employee_travel_20260907.csv` → **Download** (or open in Sheets).

**Point at** examples:
- Padded / all-caps name → **cleaned**, not rejected
- `london`, `usd`, `cancelled` lowercase → **cleaned**
- Bad date `2026-99-42` → **rejected**
- Negative `ticket_price` → **rejected**
- Duplicate `booking_id` in the same file → second row **rejected**

**Say the seven reject reasons** (same rules every day):

| Rule | Reject reason stored |
| --- | --- |
| Missing booking_id / employee_id / employee_name | `… is missing` |
| Duplicate booking_id in the file | `duplicate booking_id in source file` |
| ticket_price ≤ 0 or non-numeric | `ticket_price must be greater than zero` |
| Bad travel/return date | `travel_date` / `return_date is invalid` |
| return before travel | `return_date is earlier than travel_date` |
| status not CONFIRMED / PENDING / CANCELLED | `booking_status is invalid` |

**Expected split per daily file:** 300 read → **286 valid**, **14 rejected**.

(The older 1,000-row `data/employee_travel.csv` still exists for a bulk demo: 965 / 35. Prefer the dated files in class.)

**Ask.** Should mixed case and extra spaces be rejected?  
*Answer: No — those are fixable. We transform them. We only reject what we cannot trust.*

---

## Lesson 4 — Create dataset and 4 tables (BigQuery Console)

**Say.** Now the warehouse. One dataset, four tables, each with a job.

### Create the dataset

**Click.** ☰ → **BigQuery → Studio**. Explorer → **⋮** next to `YOUR_PROJECT_ID` → **Create dataset**.

**Type.**
- Dataset ID: `travel_analytics`
- Location: **Multi-region**, `US`
- **Create dataset**

**Point at.** Location must match `BQ_LOCATION=US` on Cloud Run.

### Create the four tables with DDL

**Say.** Real teams version schema as SQL, they do not click 40 column dialogs.

**Click.** **+ SQL query**. Copy `sql/create_tables.sql` from the repo → paste → **Run**.

**Point at** while it runs:
- `travel_staging`: partition `DATE(processed_at)`, **30-day** expiry, cluster `execution_id, booking_id`
- `employee_travel`: partition `travel_date`, cluster `department, booking_status, booking_id`
- `travel_rejected`: dates as **STRING** so invalid values survive
- `pipeline_audit`: one row per run; `file_name` stores the dated GCS path
- `ticket_price` is **FLOAT64** — "pandas + NUMERIC is a classic pyarrow foot-gun"

**Check.** Explorer shows four tables. Open `employee_travel` → **Schema**.

**Ask.** Why partition and cluster?  
*Answer: Less data scanned = cheaper and faster; clustering matches department/status filters.*

> Screenshot: `images/screenshots/bq-tables.png`

---

## Lesson 5 — Runtime service account + minimum IAM (Console)

**Say.** Cloud Run will act as its **own identity**, not as me. Three data-plane roles. **No JSON key.**

### Create the service account

**Click.** ☰ → **IAM & Admin → Service Accounts → + Create service account**.

**Type.** Name: `travel-ingestion-sa` → **Create and continue**.

### Grant the three roles

| Role | Why (say this out loud) |
| --- | --- |
| **Storage Object Viewer** | Download the dated CSV |
| **BigQuery Data Editor** | Load staging/rejected, MERGE, insert audit |
| **BigQuery Job User** | Permission to *run* BigQuery jobs |

**Click.** **Continue → Done**. **Skip the Keys tab.**

**Point at.** Empty **Keys** tab — "zero keys is the goal."

**Check.** ☰ → **IAM & Admin → IAM**, filter `travel-ingestion-sa` → three roles.

**Ask.** Why both Data Editor *and* Job User?  
*Answer: Data Editor changes table data; Job User launches the job that does it.*

> Screenshot: `images/screenshots/iam-sa.png`

---

## Lesson 6 — First (manual) deploy to Cloud Run (Console)

**Say.** First deploy is **manual** so students see Git → Docker → Artifact Registry → Cloud Run. Lesson 13 replaces this with a robot.

**Click.** Top bar → **Activate Cloud Shell** (`>_`). Still the Console — already logged in.

Upload or clone the repo in Cloud Shell (`⋮ → Upload`, or `git clone`).

**Type:**

```bash
cd gcp-travel-data-ingestion

gcloud run deploy travel-ingestion-api \
  --source . \
  --region us-central1 \
  --service-account travel-ingestion-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars GCP_PROJECT_ID=YOUR_PROJECT_ID,BQ_DATASET=travel_analytics,BQ_LOCATION=US,LOG_LEVEL=INFO \
  --allow-unauthenticated \
  --timeout 300
```

If asked to create an Artifact Registry repo, answer **Y**. (Instructor project already has `travel-platform` plus `cloud-run-source-deploy` from earlier `--source` deploys.)

**Point at.** Build log: "Building Container… Creating Revision… Routing traffic."

### After the image exists — show a UI redeploy

**Click.** ☰ → **Cloud Run → travel-ingestion-api → Edit & deploy new revision**.

**Point at.** **Variables & Secrets** (env vars) and **Security** (runtime SA). Say: "config is environment, not code."

**Check.** Copy the service URL as `YOUR_CLOUD_RUN_URL`.

**Ask.** Why inject `GCP_PROJECT_ID` instead of hardcoding it?  
*Answer: The same image can be promoted across projects.*

> Screenshot: `images/screenshots/cloud-run-service.png`

---

## Lesson 7 — Health check in the browser

**Say.** `GET /` is a liveness probe — it does **not** touch GCP.

**Click.** Open `YOUR_CLOUD_RUN_URL/` in a new tab.

**Point at.**

```json
{"service":"gcp-travel-data-ingestion","status":"UP","version":"1.0.0"}
```

**Ask.** Why should health skip BigQuery?  
*Answer: A warehouse outage should not make the *process* look down.*

---

## Lesson 8 — Trigger `/load` for one day (Cloud Shell)

**Say.** Browsers do GET easily. `/load` is POST with JSON, so Cloud Shell `curl` stays inside the Console.

**Type** — load **day 20260907** only:

```bash
URL="YOUR_CLOUD_RUN_URL"
BUCKET="YOUR_BUCKET"

curl -s -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"$BUCKET\",\"file\":\"incoming/employee_travel_20260907.csv\"}"
```

**Point at.** The SUCCESS envelope:

```json
{
  "status": "SUCCESS",
  "execution_id": "…",
  "records_read": 300,
  "records_loaded": 286,
  "records_rejected": 14,
  "processing_time": "…"
}
```

**Say.** 300 → 286 + 14. Copy `execution_id` for logs. Optional: load `_20260908.csv` and `_20260909.csv` next — **new** booking IDs, so the fact table **grows**.

**Check.** `records_loaded` = 286, `records_rejected` = 14.

**Ask.** What seven steps just ran?  
*Answer: read GCS → validate → transform → staging → MERGE → rejected → audit.*

> Screenshot: `images/screenshots/curl-success.png`

---

## Lesson 9 — Verify results in BigQuery (Console)

**Say.** Never trust SUCCESS without checking the warehouse. Dashboards read **only** `employee_travel`.

**Click.** BigQuery → Studio → new query. Run from `sql/validation_queries.sql`, one at a time.

> **Expected counts**
> | What you loaded | `employee_travel` rows |
> | --- | --- |
> | Day 20260907 only | **286** |
> | All three dated files | **858** |
> | Old 1,000-row CSV | **965** |
> Duplicates query is always **0 rows**.

**Total loaded:**

```sql
SELECT COUNT(*) AS total_loaded FROM `travel_analytics.employee_travel`;
```

**Duplicates — expect empty:**

```sql
SELECT booking_id, COUNT(*) AS occurrences
FROM `travel_analytics.employee_travel`
GROUP BY booking_id HAVING COUNT(*) > 1;
```

**Reject reasons:**

```sql
SELECT rejection_reason, COUNT(*) AS rejected_count
FROM `travel_analytics.travel_rejected`
GROUP BY rejection_reason ORDER BY rejected_count DESC;
```

**Audit — `file_name` must be the dated path:**

```sql
SELECT execution_id, file_name, status, records_read, records_loaded, records_rejected
FROM `travel_analytics.pipeline_audit`
ORDER BY start_time DESC LIMIT 5;
```

**Point at.** `file_name` = `incoming/employee_travel_20260907.csv`.

**Transform proof:**

```sql
SELECT booking_id, employee_name, origin_city, booking_status, currency, ticket_price, travel_duration_days
FROM `travel_analytics.employee_travel`
ORDER BY processed_at DESC LIMIT 5;
```

**Point at.** Title-cased names, uppercase status/currency, computed duration.

**Check.** Count matches the table above; duplicates empty; audit `SUCCESS`.

**Ask.** Which table would Looker read?  
*Answer: `employee_travel` only.*

> Screenshot: `images/screenshots/bq-validation.png`

---

## Lesson 10 — Idempotency: same day twice (Console)

**Say.** "If yesterday's file is re-sent, do we double our numbers?" Prove no.

**Predict on the board** (re-load day 20260907, 286 valid):

| Surface | After 2nd SUCCESS of the **same** day |
| --- | --- |
| `employee_travel` count | **unchanged** |
| duplicate `booking_id` | still **0** |
| `travel_rejected` | **+14** (append history) |
| `pipeline_audit` | **+1** SUCCESS (`file_name` same path) |

**Contrast:** loading `_20260908.csv` **increases** the fact table (~+286) because those booking IDs are new.

**Type** — exact same curl as Lesson 8:

```bash
curl -s -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"$BUCKET\",\"file\":\"incoming/employee_travel_20260907.csv\"}"
```

**Click.** Re-run COUNT and duplicate queries.

**Point at.** Count **unchanged**; duplicates **empty**.

**Say why** (`sql/merge_employee_travel.sql`):
1. USING only this run's staging (`WHERE execution_id = @execution_id`)
2. `ROW_NUMBER()` → one source row per `booking_id`
3. `ON booking_id` → MATCHED **UPDATE**, NOT MATCHED **INSERT**

**Ask.** Does MERGE make HTTP exactly-once?  
*Answer: No. It makes the **fact table** converge. Rejected and audit still append.*

---

## Lesson 11 — Logs and audit (Console)

**Say.** Trace every run by `execution_id`.

**Click.** ☰ → **Logging → Logs Explorer**:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="travel-ingestion-api"
```

Add `execution_id=` plus the ID from Lesson 8.

**Point at.** `File received` including the dated object name; then validation, BigQuery, `Audit written`, `Pipeline success`.

**Click.** BigQuery audit row for the same ID. **Logs = narrative. Audit = summary. `file_name` = which day.**

**Ask.** How do you tie a bad run to logs in an incident?  
*Answer: `execution_id` is in the API JSON, Cloud Logging, and `pipeline_audit`.*

> Screenshot: `images/screenshots/cloud-logging.png`

---

## Lesson 12 — Break it on purpose (Cloud Shell)

**Say.** Good pipelines fail with the right HTTP code.

**400 — missing bucket:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d '{"file":"incoming/employee_travel_20260907.csv"}'
```

**404 — wrong dated object:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"$BUCKET\",\"file\":\"incoming/employee_travel_19990101.csv\"}"
```

| HTTP | Cause |
| --- | --- |
| 400 | Bad JSON / missing `bucket` or `file` / not `.csv` |
| 403 | Runtime SA missing a role |
| 404 | Dated object not in the bucket |
| 422 | Empty CSV or missing columns |
| 500 | Tables missing / unexpected bug |

**Click.** `pipeline_audit` FAILED rows + `error_message`.

**Ask.** Why write audit on failure?  
*Answer: Ops must see the attempt, not silence.*

---

## Lesson 13 — Automate the deployment (CI/CD, Console)

**Say.** Lesson 6 was a human running Cloud Shell. Production is: **git push → Cloud Build → new Cloud Run revision**. Same three steps as [`cloudbuild.yaml`](../cloudbuild.yaml): **build image → push to Artifact Registry → `gcloud run deploy`**. Full IAM detail: [ci-cd.md](ci-cd.md).

**Point at** `cloudbuild.yaml` substitutions: `_REPOSITORY=travel-platform`, `_SERVICE=travel-ingestion-api`, `_IMAGE_TAG` (commit SHA on triggers, or passed on manual submit).

**Say the upgrade.** Manual `--source` or `:v1` is opaque. CI/CD tags `…/travel-ingestion-api:<git-sha>` so you can **roll back** to a known commit.

### 13a. IAM the Cloud Build robot (one time)

**Say.** Cloud Build is not you. It needs permission to push images, deploy Cloud Run, and **act as** `travel-ingestion-sa`.

**Click** Cloud Shell and grant (replace project / number as needed). Instructor project number is `656634452443`.

```bash
PROJECT_ID=YOUR_PROJECT_ID
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
RUNTIME_SA="travel-ingestion-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA}" --role="roles/run.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA}" --role="roles/artifactregistry.writer"
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --member="serviceAccount:${BUILD_SA}" --role="roles/iam.serviceAccountUser"
```

**Point at.** ☰ → **IAM** → `…@cloudbuild.gserviceaccount.com` now has Run Admin + Artifact Registry Writer.

**Say.** Without `serviceAccountUser` on the runtime SA, the **build succeeds** and **deploy 403s**. That is the #1 class failure.

### 13b. Artifact Registry repo (if missing)

**Click.** ☰ → **Artifact Registry → Repositories**. You should see `travel-platform` (Docker, `us-central1`) after CI, and maybe `cloud-run-source-deploy` from Lesson 6.

If `travel-platform` is missing: **Create repository** → Docker → name `travel-platform` → region `us-central1`.

### 13c. Manual Cloud Build submit (works without GitHub App)

**Say.** This is the automation we already ran in the instructor project. Same YAML as a trigger will use.

**Type** in Cloud Shell, from the repo root:

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_IMAGE_TAG=$(git rev-parse --short HEAD)
```

**Click.** ☰ → **Cloud Build → History**. Open the running build.

**Point at.** Steps `build` → `push` → `deploy`. Then **Cloud Run → Revisions** — newest revision, image in `travel-platform`.

**Check.** Build **SUCCESS**. Health URL still UP. Optional: re-run Lesson 8 curl; counts stay idempotent for the same day.

**Instructor proof already captured:** build `7732201b` SUCCESS in ~2m13s, image tag `32d0c15`, revision `travel-ingestion-api-00004-gvv`, then `/load` of `…_20260907.csv` returned 286 / 14.

### 13d. GitHub trigger so `git push` deploys (Console — required)

**Say.** `gcloud builds triggers create github` **fails** until the Cloud Build **GitHub App** is connected (`INVALID_ARGUMENT`). Students must do this in the UI.

**Click.** ☰ → **Cloud Build → Triggers → Connect repository** (or [Triggers → Create](https://console.cloud.google.com/cloud-build/triggers/add?project=gcp-evening-batch-501811) on the instructor project).

1. **GitHub (Cloud Build GitHub App)** → authorize the org/`saidhuljohny2` → select **gcp-travel-data-ingestion**.
2. **Create trigger:**
   - Name: `travel-ingestion-deploy`
   - Event: **Push to a branch**
   - Branch: `^main$`
   - Configuration: **Cloud Build configuration file** → `/cloudbuild.yaml`
   - Substitution: `_IMAGE_TAG` = `$SHORT_SHA`
3. **Create**.

**Do (live)** after the trigger exists:

```bash
git commit --allow-empty -m "ci: trigger deploy"
git push origin main
```

**Point at.** **Cloud Build → History** started by the trigger (not `gcloud builds submit`). **Cloud Run → Revisions** shows a new SHA-tagged revision.

**Check.** Trigger listed as **Enabled**. Push creates a SUCCESS build.

### 13e. GitHub Actions (mention only)

**Say.** Teams that live in GitHub can use [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) + Workload Identity Federation. Still **no JSON key**. Skip the full WIF lab unless you have 20 extra minutes ([ci-cd.md](ci-cd.md) Path B).

**Ask.** What did CI/CD change versus Lesson 6?  
*Answer: The **trigger** (push vs human), the **SHA tag** (rollback), and **repeatability**. The Docker/Cloud Run steps are the same. Still no keys.*

**Ask.** How do you roll back?  
*Answer: Deploy a previous image:  
`gcloud run deploy travel-ingestion-api --image=…/travel-ingestion-api:OLD_SHA --region=us-central1`*

---

## Lesson 14 — Interview recap and cleanup

**Interview drill.** Use the 15 Q&A in [../README.md](../README.md#interview-questions-15), plus:

1. Three runtime IAM roles and why  
2. No JSON keys / runtime SA vs Cloud Build SA  
3. MERGE + `execution_id` idempotency  
4. Dated file names vs overwrite  
5. Validate before transform  
6. `--allow-unauthenticated` vs identity token  
7. Cloud Build vs manual `--source`  
8. Why `_IMAGE_TAG=$SHORT_SHA`

### Cleanup (Console)

| Delete | Where |
| --- | --- |
| Cloud Run service | Cloud Run → **Delete** |
| BigQuery dataset | BigQuery → dataset ⋮ → **Delete dataset** |
| Bucket | Cloud Storage → bucket ⋮ → **Delete** |
| Runtime SA | IAM → Service Accounts → **Delete** |
| Cloud Build trigger | Cloud Build → Triggers → **Delete** |
| Artifact Registry | `travel-platform` and/or `cloud-run-source-deploy` → **Delete** |

**Say.** Dataset + bucket stop storage cost; Cloud Run stops request cost; leftover Artifact Registry images still bill a little.

---

## Cloud Shell vs pure clicks

Still inside the Console panel:

1. Upload local dated CSVs if drag-drop fails (`gcloud storage cp`).
2. First deploy: `gcloud run deploy --source .`
3. Automated deploy: `gcloud builds submit --config cloudbuild.yaml …`
4. GitHub trigger **must** be created in the Triggers UI after connecting the GitHub App.

Everything else (APIs, bucket, tables, IAM, health in browser, BigQuery queries, logs, cleanup) is point-and-click.

---

## 90-minute Console path

1. Enable APIs (5)  
2. Architecture + dated-file story (10)  
3. Bucket + upload three CSVs (10)  
4. Dataset + `create_tables.sql` (10)  
5. Runtime SA + 3 roles (10)  
6. Deploy `--source` (20)  
7. Health + `/load` of `_20260907.csv` (10)  
8. COUNT = 286, duplicates = 0 (5)  
9. Show Cloud Build History of a prior SUCCESS **or** run `gcloud builds submit` if time (10)

Skip: break-it, GitHub App trigger, WIF.

---

## Instructor checklist (print)

- [ ] Project selected, billing on  
- [ ] 6 APIs enabled  
- [ ] Bucket has three `incoming/employee_travel_YYYYMMDD.csv` objects  
- [ ] Dataset `travel_analytics` + 4 tables  
- [ ] `travel-ingestion-sa` with 3 roles, **no key**  
- [ ] Cloud Run up, env vars + SA set  
- [ ] `/` returns UP  
- [ ] `/load` of `_20260907.csv` returns **286 / 14**  
- [ ] BigQuery count matches days loaded; duplicates = 0  
- [ ] Second `/load` of the **same** day leaves count unchanged  
- [ ] Logs show `execution_id` + dated `File received`  
- [ ] Cloud Build SA has Run Admin + AR Writer + `serviceAccountUser` on runtime SA  
- [ ] `gcloud builds submit` SUCCESS **or** GitHub trigger connected  
- [ ] Said "demo unauthenticated" out loud  
- [ ] Cleanup or cost warning  

---

## Student homework (portfolio proof)

Screenshots from the Console:

1. GCS `incoming/` showing **three** dated objects  
2. SUCCESS JSON from `/load` of `employee_travel_20260908.csv` (286 / 14)  
3. `employee_travel` COUNT matching days loaded  
4. Duplicate query = 0 rows  
5. `pipeline_audit` with `file_name` = the dated path  
6. Paragraph: MERGE + why replaying **day 7** does not double, but loading **day 8** does add rows  
7. Paragraph: three **runtime** IAM roles  
8. Stretch: Cloud Build History SUCCESS **or** Triggers page with `travel-ingestion-deploy` enabled  
