# Automate loads: GCS upload → Eventarc → Cloud Run

The API still processes **one object per request**. This wiring removes the human `curl` for new drops:

```text
CSV uploaded to gs://BUCKET/incoming/*.csv
  → Cloud Storage object finalized
  → Eventarc
  → POST /events on Cloud Run
  → same pipeline as POST /load
```

`POST /load` stays for classroom demos, replays, and debugging.

---

## What you must deploy first

`POST /events` is in `app.py`. The running Cloud Run revision must include that code. After pulling this change:

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_IMAGE_TAG=$(git rev-parse --short HEAD)
```

Confirm the new revision, then create the trigger.

---

## IAM (no JSON keys)

Three identities:

| Identity | Role | Why |
| --- | --- | --- |
| `travel-ingestion-sa` (runtime) | Storage Object Viewer, BigQuery Data Editor, Job User | Unchanged — still downloads the CSV and writes BigQuery |
| `travel-eventarc-sa` (trigger) | Eventarc Event Receiver + Cloud Run Invoker | Eventarc uses this SA to **call** Cloud Run |
| `service-PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com` | Pub/Sub Publisher | GCS publishes the notification onto the Eventarc topic |

Never download a key. Eventarc signs the invoke as `travel-eventarc-sa`.

---

## Console (classroom path)

### 1. Enable APIs

**APIs & Services → Enable** (in addition to Lesson 0):

- Eventarc API
- Eventarc Publishing API
- Cloud Pub/Sub API

### 2. Trigger service account

**IAM & Admin → Service Accounts → Create**

- ID: `travel-eventarc-sa`
- Grant **Eventarc Event Receiver** on the project
- **Cloud Run → travel-ingestion-api → Permissions → Add principal**  
  `travel-eventarc-sa@PROJECT.iam.gserviceaccount.com` → role **Cloud Run Invoker**

### Grant **Storage Legacy Bucket Reader** on the landing bucket to `travel-eventarc-sa` (and to `service-PROJECT_NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com` if trigger create still cannot `storage.buckets.get`). Object Viewer is not enough.

### 3. Allow GCS to publish Pub/Sub

Cloud Shell (replace `PROJECT_ID`):

```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

Without this grant, trigger creation often fails with a Pub/Sub permission error.

### 4. Create the trigger

**Eventarc → Triggers → Create trigger**

| Field | Value |
| --- | --- |
| Name | `travel-gcs-incoming` |
| Event provider | **Cloud Storage** |
| Event | **google.cloud.storage.object.v1.finalized** (object finalized) |
| Bucket | `YOUR_BUCKET` |
| Path pattern (if shown) | `incoming/*.csv` |
| Destination | **Cloud Run** |
| Service | `travel-ingestion-api` |
| Path | `/events` |
| Region | **Same as the bucket** (see below) |
| Service account | `travel-eventarc-sa` |

**Trigger location must match bucket location.** A **us-central1** bucket uses trigger location `us-central1`. A **US multi-region** bucket uses trigger location `us` (not `us-central1`). Cloud Run can still live in `us-central1`.

**Check.** Trigger status **Active**. Eventarc creates a Pub/Sub topic behind the scenes.

---

## CLI (same result)

See [`scripts/setup_eventarc.sh`](../scripts/setup_eventarc.sh). Typical command after IAM:

```bash
# Regional bucket (us-central1):
gcloud eventarc triggers create travel-gcs-incoming \
  --location=us-central1 \
  --destination-run-service=travel-ingestion-api \
  --destination-run-region=us-central1 \
  --destination-run-path=/events \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=YOUR_BUCKET" \
  --event-filters-path-pattern="name=incoming/*.csv" \
  --service-account=travel-eventarc-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

If `--event-filters-path-pattern` is rejected, omit it. The API still ignores anything that is not `incoming/*.csv` and returns **204** so Eventarc does not retry.

---

## How `/events` behaves

Eventarc sends a **CloudEvent** (JSON body = GCS object metadata, `ce-type` header = `google.cloud.storage.object.v1.finalized`).

| Object | HTTP | Pipeline |
| --- | --- | --- |
| `incoming/employee_travel_20260910.csv` | 200 or 4xx/5xx from the pipeline | Runs `/load` logic |
| `incoming/` folder marker, `.txt`, root CSV | **204** empty | Skipped, no audit |
| Other event types | **204** | Skipped |

Bad CSVs still write a **FAILED** audit row (same as `/load`).

Re-uploading the same dated file is **idempotent** on `booking_id` (MERGE). You get a new audit row, not duplicate facts.

---

## Prove it

1. Generate a new day locally:  
   `python scripts/generate_sample_data.py --dates 20260910 --rows 300`
2. Console: bucket → `incoming/` → **Upload** that CSV (do **not** call curl).
3. **Cloud Run → Logs**: `Eventarc object finalized` then `File received`.
4. **BigQuery** `pipeline_audit`: newest row `file_name = incoming/employee_travel_20260910.csv`, `status = SUCCESS`.

Delivery can take **a few seconds**. If nothing happens, check trigger location vs bucket location, GCS Pub/Sub Publisher, and that the new revision exposes `/events`.

---

## Cleanup

**Eventarc → Triggers → Delete** `travel-gcs-incoming` (drops the helper Pub/Sub topic).  
**IAM → Service Accounts → Delete** `travel-eventarc-sa` if you created it only for this lab.
