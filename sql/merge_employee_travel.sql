-- Idempotent upsert. Supply execution_id as a named query parameter:
-- bq query --use_legacy_sql=false --parameter=execution_id:STRING:<UUID> \
--   < sql/merge_employee_travel.sql
--
-- booking_id is the business key. Replaying a file updates the existing record
-- rather than inserting a duplicate. ROW_NUMBER also protects the MERGE from a
-- malformed staging batch containing the same key more than once.
MERGE `travel_analytics.employee_travel` AS target
USING (
  SELECT * EXCEPT (row_number)
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY booking_id
        ORDER BY processed_at DESC
      ) AS row_number
    FROM `travel_analytics.travel_staging`
    WHERE execution_id = @execution_id
  )
  WHERE row_number = 1
) AS source
ON target.booking_id = source.booking_id
WHEN MATCHED THEN
  UPDATE SET
    employee_id = source.employee_id,
    employee_name = source.employee_name,
    department = source.department,
    origin_city = source.origin_city,
    destination_city = source.destination_city,
    travel_date = source.travel_date,
    return_date = source.return_date,
    travel_type = source.travel_type,
    airline = source.airline,
    ticket_price = source.ticket_price,
    currency = source.currency,
    booking_status = source.booking_status,
    travel_duration_days = source.travel_duration_days,
    processed_at = source.processed_at,
    source_file = source.source_file,
    execution_id = source.execution_id
WHEN NOT MATCHED THEN
  INSERT (
    booking_id, employee_id, employee_name, department, origin_city,
    destination_city, travel_date, return_date, travel_type, airline,
    ticket_price, currency, booking_status, travel_duration_days, processed_at,
    source_file, execution_id
  )
  VALUES (
    source.booking_id, source.employee_id, source.employee_name,
    source.department, source.origin_city, source.destination_city,
    source.travel_date, source.return_date, source.travel_type, source.airline,
    source.ticket_price, source.currency, source.booking_status,
    source.travel_duration_days, source.processed_at, source.source_file,
    source.execution_id
  );
