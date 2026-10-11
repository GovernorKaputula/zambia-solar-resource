SELECT city, substr(date, 1, 7) AS month,
       COUNT(*) AS days,
       AVG(ABS(ghi - prediction)) AS model_mae,
       AVG(ABS(ghi - baseline)) AS climatology_mae,
       AVG(CASE WHEN ghi BETWEEN lower AND upper THEN 1.0 ELSE 0.0 END) AS interval_coverage
FROM predictions
GROUP BY city, substr(date, 1, 7)
ORDER BY city, month;
