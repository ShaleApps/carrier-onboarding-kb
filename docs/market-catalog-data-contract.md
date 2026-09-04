# Market catalog data contract

## Purpose

Answer carrier questions about markets, commonly served facilities, historical
lane patterns, and supported equipment without exposing raw loads, customer
notes, rate cards, driver/carrier identity, or dispatch operations.

This is a live-data contract. A production KB integration must call a
migration-owned, read-only aggregate view rather than issue arbitrary LoHi SQL.

## Source model

```text
vpf.autodispatch_pool                 market label and configuration
lohiloop_load                         completed-load history and equipment
lohiloop_load_stop → tour_customer.facility
                                        facility and origin/destination history
```

The read-only validation found 81 active named pools, 54 markets with
facility history in the trailing 90 days, and 1,121 market/facility pairs with
at least ten completed loads. The data is sufficient for a filtered catalog.

## Candidate projections

### `market_summary`

- `market_id`, `market_name`, `timezone`
- `completed_load_count_28d`, `completed_load_count_90d`
- `last_completed_load_at`
- `refreshed_at`

This describes recent historical activity. It must never be phrased as a
promise of available loads, capacity, or future earnings.

### `market_facility`

- `market_id`, `facility_id`, `facility_name`, `city`, `state`
- `completed_load_count_90d`, `refreshed_at`

Only facilities with at least ten completed loads in the trailing 90 days are
eligible. Facility addresses, contacts, internal notes, appointment details,
and customer-only workflow fields are excluded.

### `market_equipment`

- `market_id`, `trailer_type`, `recent_load_count`, `refreshed_at`

Use `lohiloop_load.possible_trailer_types` for recent load requirements and
`lohiloop_load.trailer_type` for historical completed-load context. The
`possible_truck_types` field is empty in the current source and must not be
advertised as supported-equipment data.

### `market_lane_history` — internal review first

- `market_id`, origin facility, destination facility, completed-load count,
  trailing window, refreshed timestamp

This can be derived for 1,133 repeated market/lane pairs in the trailing 90
days. It is not automatically carrier-public: source owners must approve which
customer/facility names and lanes may be disclosed. Until then, the KB may say
that lane guidance is market-dependent and hand off rather than invent a lane.

## Disclosure and freshness rules

- Suppress any aggregate with fewer than ten completed loads; return no result
  rather than a thinly anonymized one.
- Use a trailing 28-day window for recent activity and a trailing 90-day window
  for facility/lane history.
- Attach a `refreshed_at` timestamp to every dynamic response.
- Do not index these volatile results as KB documents. Retrieve them through a
  scoped typed tool at answer time.
- Market data is general guidance. Carrier-specific eligibility remains a
  separate Carrier Hub decision.

## Production acceptance criteria

1. A market owner approves the customer/facility/lane disclosure policy.
2. A migration-owned LoHi view exposes only the fields above.
3. The view receives a dedicated least-privilege grant for the KB runtime role.
4. Evaluation covers an active market, a low-sample market, a missing market,
   a facility question, equipment question, and a lane question that must hand
   off pending public-lane approval.
