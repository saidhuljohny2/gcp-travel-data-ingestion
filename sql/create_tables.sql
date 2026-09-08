-- Valid records awaiting an execution-scoped merge.
CREATE TABLE IF NOT EXISTS `travel_analytics.travel_staging` (
  booking_id STRING NOT NULL,
  employee_id STRING NOT NULL,
  employee_name STRING NOT NULL,
  department STRING,
  origin_city STRING,
  destination_city STRING,
  travel_date DATE NOT NULL,
  return_date DATE NOT NULL,
  travel_type STRING,
  airline STRING,
  ticket_price FLOAT64 NOT NULL,
  currency STRING,
  booking_status STRING NOT NULL,
  travel_duration_days INT64,
  processed_at TIMESTAMP NOT NULL,
  source_file STRING NOT NULL,
  execution_id STRING NOT NULL
)
PARTITION BY DATE(processed_at)
CLUSTER BY execution_id, booking_id
OPTIONS (
  description = 'Validated execution batches used as the MERGE source',
  partition_expiration_days = 30
);

-- Current trusted record for each business key.
CREATE TABLE IF NOT EXISTS `travel_analytics.employee_travel` (
  booking_id STRING NOT NULL,
  employee_id STRING NOT NULL,
  employee_name STRING NOT NULL,
  department STRING,
  origin_city STRING,
  destination_city STRING,
  travel_date DATE NOT NULL,
  return_date DATE NOT NULL,
  travel_type STRING,
  airline STRING,
  ticket_price FLOAT64 NOT NULL,
  currency STRING,
  booking_status STRING NOT NULL,
  travel_duration_days INT64,
  processed_at TIMESTAMP NOT NULL,
  source_file STRING NOT NULL,
  execution_id STRING NOT NULL
)
PARTITION BY travel_date
CLUSTER BY department, booking_status, booking_id
OPTIONS (description = 'Clean, idempotently upserted employee travel facts');

-- Invalid source rows retain their original values for remediation.
CREATE TABLE IF NOT EXISTS `travel_analytics.travel_rejected` (
  booking_id STRING,
  employee_id STRING,
  employee_name STRING,
  department STRING,
  origin_city STRING,
  destination_city STRING,
  travel_date STRING,
  return_date STRING,
  travel_type STRING,
  airline STRING,
  ticket_price STRING,
  currency STRING,
  booking_status STRING,
  rejection_reason STRING NOT NULL,
  source_file STRING NOT NULL,
  execution_id STRING NOT NULL,
  rejected_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(rejected_at)
CLUSTER BY execution_id
OPTIONS (description = 'Rejected rows with one or more data quality reasons');

CREATE TABLE IF NOT EXISTS `travel_analytics.pipeline_audit` (
  execution_id STRING NOT NULL,
  file_name STRING,
  start_time TIMESTAMP NOT NULL,
  end_time TIMESTAMP NOT NULL,
  duration_seconds FLOAT64 NOT NULL,
  records_read INT64 NOT NULL,
  records_loaded INT64 NOT NULL,
  records_rejected INT64 NOT NULL,
  status STRING NOT NULL,
  error_message STRING
)
PARTITION BY DATE(start_time)
CLUSTER BY status, file_name
OPTIONS (description = 'One operational summary per API pipeline execution');
