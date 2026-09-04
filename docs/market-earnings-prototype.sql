-- Read-only prototype for a future LoHi migration-owned view.
-- Bind :window_start and :window_end as timestamptz values. This query returns
-- aggregate market rows only; it must not be exposed as a generic KB SQL tool.
WITH shift_loads AS (
    SELECT s.id AS shift_id, s.driver_id, p.external_title AS market,
           s.start_time, s.end_time, ls.load_id, l.completed_at
    FROM vpf.shift s
    JOIN vpf.autodispatch_pool p ON p.id = s.pool_id
    JOIN vpf.load_shift ls ON ls.shift_id = s.id AND ls.archived_at IS NULL
    JOIN lohiloop_load l ON l.id = ls.load_id AND l.cancelled_at IS NULL
    WHERE s.archived_at IS NULL
      AND s.start_time >= :window_start
      AND s.start_time < :window_end
      AND p.archived_at IS NULL
),
shift_base AS (
    SELECT shift_id, driver_id, market, start_time, end_time,
           count(DISTINCT load_id) FILTER (WHERE completed_at IS NOT NULL) AS completed_loads
    FROM shift_loads
    GROUP BY 1, 2, 3, 4, 5
),
shift_miles AS (
    SELECT sl.shift_id,
           sum(event.meters_traveled) FILTER (WHERE event.category IN (4, 5)) / 1609.344 AS miles
    FROM shift_loads sl
    JOIN vpf.load_distance_event event ON event.load_id = sl.load_id
    GROUP BY 1
),
qualified_shifts AS (
    SELECT base.shift_id, base.driver_id, base.market,
           extract(epoch FROM (base.end_time - base.start_time)) / 3600.0 AS hours
    FROM shift_base base
    LEFT JOIN shift_miles miles ON miles.shift_id = base.shift_id
    WHERE extract(epoch FROM (base.end_time - base.start_time)) / 3600.0 > 10
      AND (
          base.completed_loads >= 3
          OR (miles.miles >= 175 AND miles.miles <= extract(epoch FROM (base.end_time - base.start_time)) / 3600.0 * 75)
      )
),
latest_settlement_load AS (
    SELECT DISTINCT ON (statement_load.load_unique_id)
           statement_load.id, statement_load.load_unique_id
    FROM settlement_statement_load statement_load
    JOIN settlement_statement statement ON statement.id = statement_load.settlement_statement_id
    WHERE statement.paid_at IS NOT NULL
    ORDER BY statement_load.load_unique_id, statement.to_date DESC, statement_load.id DESC
),
base_pay_by_shift AS (
    SELECT sl.shift_id,
           sum(item.total_in_cents) FILTER (
               WHERE item.description IN (
                   'Line Haul', 'Deadhead', 'Fuel Surcharge', 'Bonus', 'Bonus Boost',
                   'Truck Ordered Not Used (TONU)', 'Detention', 'Loading Detention',
                   'Unloading Detention'
               )
           ) AS base_gross_cents
    FROM shift_loads sl
    JOIN latest_settlement_load statement_load ON statement_load.load_unique_id = sl.load_id
    JOIN settlement_statement_load_line_item item ON item.settlement_statement_load_id = statement_load.id
    GROUP BY 1
),
driver_market AS (
    SELECT shift.market, shift.driver_id, count(*) AS qualified_shifts,
           avg(pay.base_gross_cents) AS average_base_gross_cents
    FROM qualified_shifts shift
    JOIN base_pay_by_shift pay ON pay.shift_id = shift.shift_id
    GROUP BY 1, 2
)
SELECT market,
       count(*) AS eligible_driver_count,
       sum(qualified_shifts) AS settled_qualified_shift_count,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY average_base_gross_cents) / 100)::numeric, 2)
           AS median_base_gross_per_full_shift_dollars,
       round((percentile_cont(0.75) WITHIN GROUP (ORDER BY average_base_gross_cents) / 100)::numeric, 2)
           AS p75_base_gross_per_full_shift_dollars,
       round((percentile_cont(0.90) WITHIN GROUP (ORDER BY average_base_gross_cents) / 100)::numeric, 2)
           AS p90_base_gross_per_full_shift_dollars
FROM driver_market
GROUP BY market
HAVING count(*) >= 10
ORDER BY market;
