#!/usr/bin/env bash
# Create Eventarc: GCS object finalized -> Cloud Run POST /events
# Usage (Cloud Shell, from any directory):
#   export BUCKET=YOUR_BUCKET
#   bash scripts/setup_eventarc.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-us-central1}"
# Must match the bucket location: us-central1 for regional, "us" for US multi-region.
TRIGGER_LOCATION="${TRIGGER_LOCATION:-$REGION}"
SERVICE="${SERVICE:-travel-ingestion-api}"
TRIGGER="${TRIGGER:-travel-gcs-incoming}"
EVENTARC_SA_ID="${EVENTARC_SA_ID:-travel-eventarc-sa}"
BUCKET="${BUCKET:?Set BUCKET to the landing-zone bucket name}"

EVENTARC_SA="${EVENTARC_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
GCS_SA="service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com"

echo "Project=$PROJECT_ID bucket=$BUCKET trigger_location=$TRIGGER_LOCATION"

gcloud services enable \
  eventarc.googleapis.com \
  eventarcpublishing.googleapis.com \
  pubsub.googleapis.com \
  run.googleapis.com \
  storage.googleapis.com

if ! gcloud iam service-accounts describe "$EVENTARC_SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$EVENTARC_SA_ID" \
    --display-name="Eventarc invoke travel ingestion API"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${EVENTARC_SA}" \
  --role="roles/eventarc.eventReceiver" \
  --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${GCS_SA}" \
  --role="roles/pubsub.publisher" \
  --quiet

gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${EVENTARC_SA}" \
  --role="roles/run.invoker"

# storage.buckets.get is required when Eventarc validates the source bucket.
# Object Viewer does not include it; Legacy Bucket Reader does.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${EVENTARC_SA}" \
  --role="roles/storage.legacyBucketReader" \
  --quiet

EVENTARC_AGENT="service-${PROJECT_NUMBER}@gcp-sa-eventarc.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${EVENTARC_AGENT}" \
  --role="roles/eventarc.serviceAgent" \
  --quiet
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${EVENTARC_AGENT}" \
  --role="roles/storage.legacyBucketReader" \
  --quiet

set +e
gcloud eventarc triggers create "$TRIGGER" \
  --location="$TRIGGER_LOCATION" \
  --destination-run-service="$SERVICE" \
  --destination-run-region="$REGION" \
  --destination-run-path=/events \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=${BUCKET}" \
  --event-filters-path-pattern="name=incoming/*.csv" \
  --service-account="$EVENTARC_SA"
STATUS=$?
set -e

if [[ "$STATUS" -ne 0 ]]; then
  echo "Retrying without path pattern (API still filters incoming/*.csv)..."
  gcloud eventarc triggers create "$TRIGGER" \
    --location="$TRIGGER_LOCATION" \
    --destination-run-service="$SERVICE" \
    --destination-run-region="$REGION" \
    --destination-run-path=/events \
    --event-filters="type=google.cloud.storage.object.v1.finalized" \
    --event-filters="bucket=${BUCKET}" \
    --service-account="$EVENTARC_SA"
fi

gcloud eventarc triggers describe "$TRIGGER" --location="$TRIGGER_LOCATION"
echo "Upload incoming/*.csv to gs://${BUCKET}/incoming/ — do not curl /load."
