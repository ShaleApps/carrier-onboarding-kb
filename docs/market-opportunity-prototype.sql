-- Read-only prototype for carrier_kb_public_market_opportunity_v1.
-- This query intentionally produces a coarse demand band, not individual
-- load details, rates, routes, or booking eligibility.
WITH current_loads AS (
    SELECT sourced_for_vpf_pool_id, possible_trailer_types
    FROM lohiloop_load
    WHERE cancelled_at IS NULL
      AND completed_at IS NULL
      AND is_auto_dispatchable IS TRUE
      AND updated_at >= now() - interval '28 days'
      AND sourced_for_vpf_pool_id IS NOT NULL
),
market_load_counts AS (
    SELECT sourced_for_vpf_pool_id AS market_id, count(*) AS load_count
    FROM current_loads
    GROUP BY 1
),
market_equipment AS (
    SELECT loads.sourced_for_vpf_pool_id AS market_id,
           equipment.trailer_type::text AS trailer_type,
           count(*) AS recent_load_count
    FROM current_loads loads
    CROSS JOIN LATERAL unnest(loads.possible_trailer_types) AS equipment(trailer_type)
    GROUP BY 1, 2
    HAVING count(*) >= 3
)
SELECT pool.id AS market_id,
       pool.external_title AS market_name,
       CASE
           WHEN coalesce(counts.load_count, 0) = 0 THEN 'none'
           WHEN counts.load_count < 10 THEN 'limited'
           ELSE 'active'
       END AS availability,
       coalesce(jsonb_agg(DISTINCT jsonb_build_object(
           'trailer_type', equipment.trailer_type,
           'recent_load_count', equipment.recent_load_count
       )) FILTER (WHERE equipment.trailer_type IS NOT NULL), '[]'::jsonb) AS equipment,
       now() AS refreshed_at
FROM vpf.autodispatch_pool pool
LEFT JOIN market_load_counts counts ON counts.market_id = pool.id
LEFT JOIN market_equipment equipment ON equipment.market_id = pool.id
WHERE pool.archived_at IS NULL
GROUP BY pool.id, pool.external_title, counts.load_count;
