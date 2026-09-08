-- Run with: bq query --use_legacy_sql=false < sql/create_dataset.sql
-- The dataset is created in the active gcloud project.
CREATE SCHEMA IF NOT EXISTS `travel_analytics`
OPTIONS (
  location = 'US',
  description = 'Curated employee travel data and pipeline operations'
);
