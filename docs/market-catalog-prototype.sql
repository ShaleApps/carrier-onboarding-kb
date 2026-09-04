-- Read-only prototype for future LoHi migration-owned projections.
-- The query is intentionally aggregate-only. Bind :recent_start and
-- :history_start as timestamptz values before execution.
WITH recent_loads AS (
    SELECT id, sourced_for_vpf_pool_id, possible_trailer_types, updated_at
    FROM lohiloop_load
    WHERE cancelled_at IS NULL
      AND updated_at >= :recent_start
      AND sourced_for_vpf_pool_id IS NOT NULL
),
history_loads AS (
    SELECT id, sourced_for_vpf_pool_id, completed_at
    FROM lohiloop_load
    WHERE cancelled_at IS NULL
      AND completed_at >= :history_start
      AND sourced_for_vpf_pool_id IS NOT NULL
),
market_summary AS (
    SELECT pool.id AS market_id, pool.external_title AS market_name, pool.timezone,
           count(DISTINCT recent.id) AS recent_load_count,
           count(DISTINCT history.id) AS completed_load_count_90d,
           max(history.completed_at) AS last_completed_load_at
    FROM vpf.autodispatch_pool pool
    LEFT JOIN recent_loads recent ON recent.sourced_for_vpf_pool_id = pool.id
    LEFT JOIN history_loads history ON history.sourced_for_vpf_pool_id = pool.id
    WHERE pool.archived_at IS NULL
    GROUP BY 1, 2, 3
),
facility_history AS (
    SELECT history.sourced_for_vpf_pool_id AS market_id, facility.id AS facility_id,
           facility.name AS facility_name, facility.address_city AS city,
           facility.address_state AS state, count(DISTINCT history.id) AS completed_load_count_90d
    FROM history_loads history
    JOIN lohiloop_load_stop stop ON stop.load_id = history.id AND stop.archived_at IS NULL
    JOIN tour_customer.facility facility ON facility.id = stop.facility_id AND facility.archived_at IS NULL
    GROUP BY 1, 2, 3, 4, 5
    HAVING count(DISTINCT history.id) >= 10
),
equipment_history AS (
    SELECT recent.sourced_for_vpf_pool_id AS market_id,
           equipment.trailer_type::text AS trailer_type,
           count(DISTINCT recent.id) AS recent_load_count
    FROM recent_loads recent
    CROSS JOIN LATERAL unnest(recent.possible_trailer_types) AS equipment(trailer_type)
    GROUP BY 1, 2
    HAVING count(DISTINCT recent.id) >= 10
)
SELECT summary.market_id, summary.market_name, summary.timezone,
       summary.recent_load_count, summary.completed_load_count_90d,
       summary.last_completed_load_at,
       coalesce(jsonb_agg(DISTINCT jsonb_build_object(
           'facility_id', facility.facility_id,
           'name', facility.facility_name,
           'city', facility.city,
           'state', facility.state,
           'completed_load_count_90d', facility.completed_load_count_90d
       )) FILTER (WHERE facility.facility_id IS NOT NULL), '[]'::jsonb) AS facilities,
       coalesce(jsonb_agg(DISTINCT jsonb_build_object(
           'trailer_type', equipment.trailer_type,
           'recent_load_count', equipment.recent_load_count
       )) FILTER (WHERE equipment.trailer_type IS NOT NULL), '[]'::jsonb) AS equipment,
       now() AS refreshed_at
FROM market_summary summary
LEFT JOIN facility_history facility ON facility.market_id = summary.market_id
LEFT JOIN equipment_history equipment ON equipment.market_id = summary.market_id
GROUP BY 1, 2, 3, 4, 5, 6;
