-- 1. Total loaded records
SELECT COUNT(*) AS total_loaded FROM `travel_analytics.employee_travel`;

-- 2. Duplicate booking IDs (expected: zero rows)
SELECT booking_id, COUNT(*) AS occurrences
FROM `travel_analytics.employee_travel`
GROUP BY booking_id HAVING COUNT(*) > 1;

-- 3. Rejected records
SELECT rejection_reason, COUNT(*) AS rejected_count
FROM `travel_analytics.travel_rejected`
GROUP BY rejection_reason ORDER BY rejected_count DESC;

-- 4. Department-wise travel spend
SELECT department, currency, ROUND(SUM(ticket_price), 2) AS total_spend
FROM `travel_analytics.employee_travel`
GROUP BY department, currency ORDER BY total_spend DESC;

-- 5. Airline-wise spend
SELECT airline, currency, ROUND(SUM(ticket_price), 2) AS total_spend
FROM `travel_analytics.employee_travel`
GROUP BY airline, currency ORDER BY total_spend DESC;

-- 6. Average travel duration
SELECT ROUND(AVG(travel_duration_days), 2) AS average_travel_duration_days
FROM `travel_analytics.employee_travel`;

-- 7. Cancelled bookings
SELECT * FROM `travel_analytics.employee_travel`
WHERE booking_status = 'CANCELLED' ORDER BY travel_date DESC;

-- 8. Pending bookings
SELECT * FROM `travel_analytics.employee_travel`
WHERE booking_status = 'PENDING' ORDER BY travel_date DESC;

-- 9. Pipeline audit history
SELECT * FROM `travel_analytics.pipeline_audit` ORDER BY start_time DESC;

-- 10. Latest successful execution
SELECT * FROM `travel_analytics.pipeline_audit`
WHERE status = 'SUCCESS' ORDER BY start_time DESC LIMIT 1;
