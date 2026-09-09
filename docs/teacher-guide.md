# Teacher Guide (Console Edition) — GCP Travel Data Ingestion Platform

Run the **entire project from the Google Cloud Console (browser UI)** in front of students. This guide tells you **where to click**, **what to type in each dialog**, **what to point at on screen**, and **what to say**. The CLI is used only when the Console cannot do a step (there is exactly one: uploading the local CSV and deploying container source — both have Console-friendly options below).

Each step has:

- **Say** — talking points
- **Click** — exact Console navigation
- **Type** — values to enter (replace `YOUR_*`)
- **Point at** — what to highlight on screen
- **Check** — proof it worked
- **Ask** — one question to lock the concept

Related: [../README.md](../README.md), [architecture.md](architecture.md), [deployment-guide.md](deployment-guide.md).

> **Placeholders**
> - `YOUR_PROJECT_ID` — your GCP project
> - `YOUR_BUCKET` — globally unique, suggest `travel-incoming-YOUR_PROJECT_ID`
> - `YOUR_REGION` — `us-central1`
> - `YOUR_CLOUD_RUN_URL` — appears after deploy, ends `.run.app`
>
> **Say every deploy:** "Unauthenticated access is a classroom demo only. In production we require an identity token." **Never create a service-account JSON key.**

---

## Before class — instructor prep (do NOT do live)

Cloud Build container builds are slow (3–8 min). Pre-warm so class does not stall:

- Confirm the project has **billing enabled**.
- Have the repo open locally (you will drag `data/employee_travel.csv` into the Console upload dialog).
- Optionally deploy once the day before to prime Artifact Registry, then delete the service so students see it built live — your call.
- Open these Console tabs in advance:
  1. **APIs & Services**
  2. **Cloud Storage → Buckets**
  3. **BigQuery → Studio**
  4. **IAM & Admin → Service Accounts**
  5. **Cloud Run**
  6. **Logging → Logs Explorer**

**One-time truth to teach:** the whole project is 5 Console areas — **Storage, BigQuery, IAM, Cloud Run, Logging**. Draw those 5 boxes first.

---

## Session map (Console demo)

| # | Lesson | Console area | Time |
| --- | --- | --- | --- |
| 0 | Pick project, enable APIs | APIs & Services | 10 min |
| 1 | Business + architecture | (slides) | 20 min |
| 2 | Create bucket, upload CSV | Cloud Storage | 15 min |
| 3 | Look at the dirty data | Cloud Storage / Sheets | 15 min |
| 4 | Create dataset + 4 tables | BigQuery Studio | 25 min |
| 5 | Create runtime service account + roles | IAM & Admin | 20 min |
| 6 | Deploy the API | Cloud Run | 30 min |
| 7 | Health check in browser | Cloud Run URL | 5 min |
| 8 | Trigger `/load` (Cloud Shell curl) | Cloud Shell | 15 min |
| 9 | Verify results | BigQuery Studio | 20 min |
| 10 | Replay = idempotency | Cloud Run + BigQuery | 15 min |
| 11 | Read the logs + audit | Logs Explorer | 15 min |
| 12 | Break it on purpose | Cloud Shell | 10 min |
| 12b | Automate deployment (CI/CD) | Cloud Build / GitHub | 20 min |
| 13 | Interview recap + cleanup | (slides) / all areas | 20 min |

Total ≈ 4 hours. 90-minute path is at the end.

---

## Lesson 0 — Project and APIs (Console)

**Say.** Everything we build lives inside one project. First we turn on the Google services we need.

**Click.** Top blue bar → **project picker** → select `YOUR_PROJECT_ID`.

**Click.** Navigation menu (☰) → **APIs & Services → Enabled APIs & services → + Enable APIs and Services**.

**Type / enable** these one by one (search each, click **Enable**):

- Cloud Run Admin API
- Artifact Registry API
- Cloud Build API
- Cloud Storage
- BigQuery API
- Identity and Access Management (IAM) API

**Point at.** The green checkmarks on the Enabled APIs list.

**Check.** All six show as enabled.

**Ask.** Why must we enable APIs before using a service?  
*Answer: GCP disables most APIs by default for security and billing control.*

> Screenshot: `images/screenshots/enabled-apis.png`

---

## Lesson 1 — Business problem and architecture (slides / whiteboard)

**Say.**

- A company drops a daily CSV into Cloud Storage `incoming/`.
- Analysts need **clean** bookings in BigQuery, not raw garbage.
- Engineering exposes a REST API on **Cloud Run** so anything can trigger a load.
- Re-running the same file must **not** duplicate `booking_id`.

**Point at.** `images/architecture.png`, then whiteboard two arrows:

```text
Deploy:  Git → Docker → Artifact Registry → Cloud Run
Data:    GCS CSV → Cloud Run (validate + transform) → BigQuery
```

**Say the four tables:**

| Table | Audience | Behavior |
| --- | --- | --- |
| `travel_staging` | Engineers | Append this run's valid rows |
| `employee_travel` | Analysts | Current truth; MERGE on `booking_id` |
| `travel_rejected` | Data owners | Bad rows + reason |
| `pipeline_audit` | Ops | One row per run |

**Ask.** Why not load the CSV straight into BigQuery with autodetect?  
*Answer: No validation reasons, no transform, duplicates on replay, no audit.*

---

## Lesson 2 — Create the bucket and upload the CSV (Console)

**Say.** This bucket is the landing zone. The daily file will live under `incoming/`.

### Create the bucket

**Click.** ☰ → **Cloud Storage → Buckets → + Create**.

**Type.**
- Name: `YOUR_BUCKET` (must be globally unique)
- Location type: **Multi-region**, `US` (match BigQuery `US`)
- Leave **Uniform** access control (recommended)
- Click **Create**. If prompted about public access prevention, keep it **on**.

**Point at.** Uniform access control — say "no per-object ACLs, IAM decides who reads."

### Create the folder and upload daily files

**Say.** Production files arrive **daily** with a date in the name: `employee_travel_YYYYMMDD.csv`. We ship three ready-made days in `data/incoming/`.

**Click.** Open the bucket → **Create folder** → name it `incoming` → **Create**.

**Click.** Open `incoming` → **Upload files** → select all three from the repo's `data/incoming/`:
- `employee_travel_20260907.csv`
- `employee_travel_20260908.csv`
- `employee_travel_20260909.csv`

**Point at.** The object paths become `incoming/employee_travel_2026090X.csv`. Say: "The API takes any file name; the date lets us load one specific day."

**Check.** Three dated objects inside `incoming/` (each ~300 rows).

**Ask.** Why put a timestamp in the file name instead of overwriting one file?  
*Answer: Traceability and replay — each day is auditable, and `pipeline_audit.file_name` records exactly which day loaded.*

> Need more days live? In Cloud Shell: `python scripts/generate_sample_data.py --dates 20260910 --rows 300` then upload.

> Screenshot: `images/screenshots/gcs-object.png`

> If drag-and-drop upload is blocked, use Cloud Shell:
> `gcloud storage cp data/incoming/*.csv gs://YOUR_BUCKET/incoming/`

---

## Lesson 3 — Look at the dirty data (Console)

**Say.** Real files are messy. This sample is **designed** to fail some rows so the reject table is not empty.

**Click.** In the bucket, click `employee_travel.csv` → **Download** (or open in Sheets) so students see the raw rows.

**Point at** examples:
- A padded / all-caps name (extra spaces) → will be **cleaned**, not rejected
- `london`, `usd`, `confirmed` lowercase → **cleaned**
- A bad date like `2026-99-42` → **rejected**
- A negative or zero `ticket_price` → **rejected**
- Two rows with the same `booking_id` → second is **rejected**

**Say the rule summary (7 reject reasons):**

| Rule | Reject reason stored |
| --- | --- |
| Missing booking_id / employee_id / employee_name | `… is missing` |
| Duplicate booking_id in the file | `duplicate booking_id in source file` |
| ticket_price ≤ 0 or non-numeric | `ticket_price must be greater than zero` |
| Bad travel/return date | `travel_date` / `return_date is invalid` |
| return before travel | `return_date is earlier than travel_date` |
| status not CONFIRMED/PENDING/CANCELLED | `booking_status is invalid` |

**Expected split:** 1000 read → **965 valid**, **35 rejected**.

**Ask.** Should mixed case and extra spaces be rejected?  
*Answer: No — those are fixable, so we transform them. We only reject what we cannot trust.*

---

## Lesson 4 — Create dataset and 4 tables (BigQuery Console)

**Say.** Now the warehouse. One dataset, four tables, each with a job.

### Create the dataset

**Click.** ☰ → **BigQuery → Studio**. In Explorer, click the **⋮** next to `YOUR_PROJECT_ID` → **Create dataset**.

**Type.**
- Dataset ID: `travel_analytics`
- Location type: **Multi-region**, `US`
- **Create dataset**

**Point at.** Location must match what the API sends (`BQ_LOCATION=US`).

### Create the four tables with DDL

**Say.** Instead of clicking table-by-table, we run the DDL script — this is how real teams version schema.

**Click.** **+ SQL query** (compose new query). Open `sql/create_tables.sql` from the repo, copy all of it, paste into the editor.

**Point at** while it runs, teach the design:
- `travel_staging`: partitioned by `DATE(processed_at)`, **30-day** expiry, cluster by `execution_id, booking_id` — cheap to debug, auto-cleans.
- `employee_travel`: partitioned by `travel_date`, clustered by `department, booking_status, booking_id` — matches the spend queries.
- `travel_rejected`: dates stored as **STRING** so invalid values survive.
- `pipeline_audit`: one row per run.
- Note `ticket_price` is **FLOAT64** — say "pandas + BigQuery NUMERIC is a classic byte-length trap; FLOAT64 avoids it."

**Click.** **Run**.

**Check.** Expand `travel_analytics` in Explorer → four tables appear. Click `employee_travel` → **Schema** tab → show columns and types.

**Ask.** Why partition and cluster instead of one flat table?  
*Answer: Less data scanned = cheaper, faster queries; clustering speeds the department/status filters.*

> Screenshot: `images/screenshots/bq-tables.png`

---

## Lesson 5 — Runtime service account + minimum IAM (Console)

**Say.** Cloud Run will act as its **own identity**, not as me. We give that identity exactly three data-plane roles — nothing more. And we create **no JSON key**.

### Create the service account

**Click.** ☰ → **IAM & Admin → Service Accounts → + Create service account**.

**Type.**
- Name: `travel-ingestion-sa`
- **Create and continue**

### Grant the three roles

On the **Grant this service account access** step, add three roles (click **+ Add another role** each time):

| Role | Why (say this out loud) |
| --- | --- |
| **Storage Object Viewer** | Download the CSV from the bucket |
| **BigQuery Data Editor** | Load staging/rejected, MERGE, insert audit |
| **BigQuery Job User** | Permission to *run* BigQuery jobs |

**Click.** **Continue → Done**. **Skip the Keys tab entirely.**

**Point at.** The empty **Keys** tab on the SA — say "zero keys, this is the goal."

**Check.** ☰ → **IAM & Admin → IAM**, filter for `travel-ingestion-sa` → three roles listed.

**Ask.** Why both Data Editor *and* Job User?  
*Answer: Data Editor changes table data; Job User lets you launch the load/query job that does it.*

> Screenshot: `images/screenshots/iam-sa.png`

---

## Lesson 6 — Deploy the API to Cloud Run (Console)

**Say.** Cloud Run needs a container image. We'll let Google build it from source — no Docker on my laptop.

There are two Console paths. **Path A** is fully in the browser.

### Path A — Cloud Run "deploy from source repository" is not always available; use Cloud Shell build-and-deploy from the Console

**Click.** Top bar → **Activate Cloud Shell** (`>_` icon). A terminal opens **inside the Console**.

**Say.** Cloud Shell is still the Console — a browser terminal Google gives us, already authenticated as me.

**Type** in Cloud Shell (upload the repo first with the Cloud Shell **⋮ → Upload**, or `git clone` your repo):

```bash
cd gcp-travel-data-ingestion   # your repo folder in Cloud Shell

gcloud run deploy travel-ingestion-api \
  --source . \
  --region us-central1 \
  --service-account travel-ingestion-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars GCP_PROJECT_ID=YOUR_PROJECT_ID,BQ_DATASET=travel_analytics,BQ_LOCATION=US,LOG_LEVEL=INFO \
  --allow-unauthenticated \
  --timeout 300
```

If it asks to create an Artifact Registry repo, answer **Y**.

**Point at.** The build log lines: "Building Container… Creating Revision… Routing traffic." This is Git→Docker→Artifact Registry→Cloud Run happening live.

### Path B — after the image exists, redeploys are pure UI

Once an image is in Artifact Registry, you can redeploy from the Console:

**Click.** ☰ → **Cloud Run → travel-ingestion-api → Edit & deploy new revision**. Show the **Variables & Secrets** tab (env vars) and **Security** tab (service account). This is the teaching moment for "config is environment, not code."

**Check.** Cloud Run service page shows a green check and a **URL** ending in `.run.app`. Copy it as `YOUR_CLOUD_RUN_URL`.

**Point at.** Revisions tab → the service account and env vars on the revision.

**Ask.** Why inject `GCP_PROJECT_ID` as an env var instead of hardcoding it?  
*Answer: The same image can be promoted across dev/prod projects.*

> Screenshot: `images/screenshots/cloud-run-service.png`

---

## Lesson 7 — Health check in the browser

**Say.** The `/` endpoint is a liveness probe — it does **not** touch GCP, so it proves the container is up.

**Click.** Open `YOUR_CLOUD_RUN_URL/` in a new browser tab.

**Point at.** JSON in the browser:

```json
{"service":"gcp-travel-data-ingestion","status":"UP","version":"1.0.0"}
```

**Ask.** Why should a health check avoid calling BigQuery?  
*Answer: A slow/broken dependency shouldn't make the platform look "down"; health = process alive.*

---

## Lesson 8 — Trigger the pipeline `POST /load` (Cloud Shell)

**Say.** `/` was GET in a browser. `/load` is POST with a JSON body, so we use Cloud Shell curl (still inside the Console).

**Type** in Cloud Shell — load **one specific day** by its dated file name:

```bash
URL="YOUR_CLOUD_RUN_URL"
BUCKET="YOUR_BUCKET"

curl -s -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"$BUCKET\",\"file\":\"incoming/employee_travel_20260907.csv\"}"
```

**Point at.** The SUCCESS envelope (300-row daily file):

```json
{"status":"SUCCESS","execution_id":"…","records_read":300,"records_loaded":286,"records_rejected":14,"processing_time":"… seconds"}
```

**Say.** Read it left to right: 300 read → 286 loaded → 14 rejected. Copy the `execution_id`; we'll trace it in logs. Then load day 2 and day 3 by changing the date in the file name — each day adds new bookings.

**Check.** `records_loaded` = 286, `records_rejected` = 14 for a daily file.

**Ask.** What are the seven pipeline steps that just ran?  
*Answer: read GCS → validate → transform → staging load → MERGE → rejected load → audit.*

> Screenshot: `images/screenshots/curl-success.png`

---

## Lesson 9 — Verify results in BigQuery (Console)

**Say.** Never trust a "SUCCESS" without checking the warehouse. Analysts only read `employee_travel`.

**Click.** BigQuery → Studio → new query. Run each (from `sql/validation_queries.sql`), one at a time, narrating.

> **Numbers depend on what you loaded.** One daily file = **286**. All three daily files (distinct booking IDs) = **858**. The original `employee_travel.csv` = **965**. What never changes: duplicates stay **0**.

**Total loaded:**

```sql
SELECT COUNT(*) AS total_loaded FROM `travel_analytics.employee_travel`;
```

**Duplicate booking IDs — expect zero rows:**

```sql
SELECT booking_id, COUNT(*) AS occurrences
FROM `travel_analytics.employee_travel`
GROUP BY booking_id HAVING COUNT(*) > 1;
```

**Why rows were rejected:**

```sql
SELECT rejection_reason, COUNT(*) AS rejected_count
FROM `travel_analytics.travel_rejected`
GROUP BY rejection_reason ORDER BY rejected_count DESC;
```

**Proof the run happened (audit):**

```sql
SELECT execution_id, status, records_read, records_loaded, records_rejected, duration_seconds
FROM `travel_analytics.pipeline_audit`
ORDER BY start_time DESC LIMIT 5;
```

**Show the transform worked:**

```sql
SELECT booking_id, employee_name, origin_city, booking_status, currency, ticket_price, travel_duration_days
FROM `travel_analytics.employee_travel`
ORDER BY processed_at DESC LIMIT 5;
```

**Point at.** Title-cased names, uppercase status/currency, `travel_duration_days` computed.

**Check.** Row count matches what you loaded (286 for one day); duplicate query empty; reject reasons listed; audit row `SUCCESS`.

**Ask.** Which table would a Looker/Data Studio dashboard read?  
*Answer: `employee_travel` only.*

> Screenshot: `images/screenshots/bq-validation.png`

---

## Lesson 10 — Idempotency: run the same file twice (Console)

**Say.** The scary question: "If yesterday's file is re-sent, do we double our numbers?" Let's prove no.

**Before running, predict on the board** (re-loading day 1, which had 286 valid):

| Surface | After a 2nd SUCCESS of the same day |
| --- | --- |
| `employee_travel` count | **unchanged** (still 286 for that day's IDs) |
| duplicate booking_id | still **0** |
| `travel_rejected` | **+14** (append history) |
| `pipeline_audit` | **+1** SUCCESS row |

**Type** in Cloud Shell — the exact same command as Lesson 8 (same dated file):

```bash
curl -s -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"$BUCKET\",\"file\":\"incoming/employee_travel_20260907.csv\"}"
```

**Click.** Re-run the **total loaded** and **duplicate** queries in BigQuery.

**Point at.** Count is **unchanged**; duplicates **still empty**.

**Say why (the MERGE):** open `sql/merge_employee_travel.sql`. Explain:
1. USING only this run's staging rows (`WHERE execution_id = @execution_id`)
2. `ROW_NUMBER()` keeps one row per `booking_id`
3. `ON booking_id` → MATCHED **updates**, NOT MATCHED **inserts**

**Ask.** Does MERGE make the HTTP call exactly-once?  
*Answer: No — it makes the **fact table** converge. Rejected/audit intentionally append as history.*

---

## Lesson 11 — Logs and audit (Console)

**Say.** Every run is traceable by `execution_id`.

**Click.** ☰ → **Logging → Logs Explorer**. In the query box:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="travel-ingestion-api"
```

Then add `execution_id=` and paste the ID from Lesson 8.

**Point at** the ordered log lines: `API started`, `File received`, `Validation started/completed`, `BigQuery … load started/completed`, `Audit written`, `Pipeline success`.

**Say.** Notice levels: INFO for flow, WARNING for rejected counts, ERROR for failures.

**Click.** Back to BigQuery, show the audit row for that same `execution_id`. Connect: **logs = narrative, audit table = summary**.

**Ask.** In an incident, how do you tie a bad run to its logs?  
*Answer: `execution_id` is in the API response, the logs, and `pipeline_audit`.*

> Screenshot: `images/screenshots/cloud-logging.png`

---

## Lesson 12 — Break it on purpose (Cloud Shell)

**Say.** Good pipelines fail loudly and correctly. Watch the HTTP codes.

**400 — missing bucket:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d '{"file":"incoming/employee_travel.csv"}'
```

**404 — wrong object:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/load" \
  -H "Content-Type: application/json" \
  -d "{\"bucket\":\"$BUCKET\",\"file\":\"incoming/nope.csv\"}"
```

**Say the map:**

| HTTP | Cause |
| --- | --- |
| 400 | Bad JSON / missing bucket or file / not `.csv` |
| 403 | Runtime SA missing a role |
| 404 | Object not found |
| 422 | Empty CSV or missing columns |
| 500 | Tables missing / unexpected bug |

**Click.** BigQuery → `pipeline_audit` → show FAILED rows with `error_message`.

**Ask.** Why still write an audit row on failure?  
*Answer: Ops needs to know a run was attempted and why it failed, not just silence.*

---

## Lesson 12b — Automate the deployment (CI/CD)

**Say.** We deployed by hand. In a real team nobody redeploys manually — a **push to `main`** rebuilds and redeploys. Same steps, run by a robot. Full setup: [ci-cd.md](ci-cd.md).

**Point at.** [`cloudbuild.yaml`](../cloudbuild.yaml). Say: "This is exactly what we did by hand — build, push to Artifact Registry, deploy to Cloud Run — written down so it repeats."

**Say the key upgrade.** Manual deploy tagged the image `:v1`. CI/CD tags it with the **commit SHA**, so every deploy is traceable and any old version can be rolled back.

### Path A — Cloud Build trigger (all in Console)

**Click.** ☰ → **Cloud Build → Triggers → Connect repository** → **GitHub** → authorize → pick the repo.

**Click.** **Create trigger**:
- Event: **Push to a branch**
- Branch: `^main$`
- Configuration: **Cloud Build configuration file** → `/cloudbuild.yaml`
- **Create**.

**Say the IAM (one time).** The Cloud Build service account needs **Cloud Run Admin**, **Artifact Registry Writer**, and **Service Account User** on the runtime SA (commands in [ci-cd.md](ci-cd.md) §A1). Without those the build succeeds but the deploy step 403s.

**Do (live).** Make a trivial commit and push:

```bash
git commit --allow-empty -m "ci: trigger deploy"
git push origin main
```

**Point at.** **Cloud Build → History** running; then **Cloud Run → Revisions** shows a new SHA-tagged revision.

**Check.** New revision serving 100% traffic, created by Cloud Build (not you).

### Path B — GitHub Actions, keyless (mention)

**Say.** If the team lives in GitHub, use [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) with **Workload Identity Federation** — GitHub's OIDC token is swapped for short-lived Google creds. **Still no JSON key.** One-time pool/provider setup is in [ci-cd.md](ci-cd.md) §B.

**Ask.** What did CI/CD change versus our manual deploy?  
*Answer: The trigger (git push), the SHA image tag (traceable + rollbackable), and consistency — the steps are identical every time. No keys either way.*

---

## Lesson 13 — Interview recap and cleanup

**Interview drill (Console-friendly picks).** Use the 15 Q&A in [../README.md](../README.md#interview-questions-15). Prioritize:
1. Three IAM roles and why
2. No JSON keys / runtime SA
3. MERGE + `execution_id` idempotency
4. Validate before transform
5. `--allow-unauthenticated` vs identity token
6. Partition/cluster choices

### Cleanup (all in Console)

| Delete | Where |
| --- | --- |
| Cloud Run service | Cloud Run → select service → **Delete** |
| BigQuery dataset | BigQuery → dataset ⋮ → **Delete dataset** |
| Bucket | Cloud Storage → bucket ⋮ → **Delete** |
| Service account | IAM & Admin → Service Accounts → **Delete** |
| (Optional) Cloud Build trigger | Cloud Build → Triggers → **Delete** |
| (Optional) Artifact Registry repo | Artifact Registry → `cloud-run-source-deploy` (or `travel-platform`) → **Delete** |

**Say.** Deleting the dataset and bucket stops storage cost; deleting Cloud Run stops request cost.

---

## The one place you must leave the Console

Two actions the browser UI cannot do cleanly, both handled in **Cloud Shell** (still a Console panel):

1. Uploading the **local** repo CSV (drag-drop into the bucket usually works; Cloud Shell `gcloud storage cp` is the fallback).
2. **Building the container from source** — `gcloud run deploy --source .` runs the build via Cloud Build.

Everything else (project, APIs, bucket create, dataset, tables, IAM, deploy config, verification, logs, cleanup) is pure point-and-click.

---

## 90-minute Console-only path

1. Enable APIs (5)
2. Architecture + dirty data story (15)
3. Bucket + upload CSV (10)
4. Dataset + run `create_tables.sql` (15)
5. Service account + 3 roles (10)
6. Deploy via Cloud Shell (20)
7. Health in browser + one dated `/load` (10)
8. Two BigQuery queries: total loaded (286 for one day), duplicates 0 (5)

Skip: local Flask, local Docker, break-it lesson, deep log tour.

---

## Instructor checklist (print)

- [ ] Project selected, billing on
- [ ] 6 APIs enabled
- [ ] Bucket created, daily `incoming/employee_travel_YYYYMMDD.csv` files uploaded
- [ ] Dataset `travel_analytics` + 4 tables
- [ ] `travel-ingestion-sa` with 3 roles, **no key**
- [ ] Cloud Run deployed, env vars + SA set
- [ ] `/` returns UP in browser
- [ ] `/load` of a daily file returns 286 / 14
- [ ] BigQuery count matches loaded files, duplicates = 0
- [ ] Second `/load` of same day leaves count unchanged
- [ ] Logs show `execution_id` + `Pipeline success`
- [ ] (Optional) Cloud Build trigger redeploys on `git push`
- [ ] Said "demo unauthenticated" out loud
- [ ] Cleanup done or cost warned

---

## Student homework (portfolio proof)

Submit screenshots from the Console:
1. SUCCESS JSON from `/load` of a dated file (e.g. `employee_travel_20260908.csv`)
2. `employee_travel` count matching the days you loaded
3. Duplicate query = 0 rows
4. `pipeline_audit` showing one SUCCESS row per day, with `file_name` = the dated file
5. One paragraph: how the MERGE prevented duplicates
6. One paragraph: the three IAM roles and why each is needed
7. Stretch: a screenshot of a Cloud Build run that deployed on `git push`
