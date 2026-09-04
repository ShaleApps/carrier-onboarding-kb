# Market opportunity data contract

## Purpose

Provide a current market-demand signal for carrier questions such as "is this
market active?" without exposing individual loads, customers, facilities,
rates, lane details, or dispatch controls.

## Candidate v1 projection

`carrier_kb_public_market_opportunity_v1` returns one row per market:

- `market_id`, `market_name`
- `availability`: `none`, `limited`, or `active`
- `equipment`: recent supported trailer types with their aggregate load count
- `refreshed_at`

`availability` is based on current, uncompleted, non-cancelled
`lohiloop_load` records where `is_auto_dispatchable` is true:

- `none`: zero qualifying records
- `limited`: one to nine qualifying records
- `active`: ten or more qualifying records

It is a point-in-time signal, not a guarantee that a carrier can book a load.
Carrier-specific eligibility and assignment remain outside this view.

## Rate and pay boundary

LoHi's current `rate_cents` field is a customer rate. It must not be presented
as a carrier pay quote or transformed into one by the KB. `carrier_cents_override`
is not populated for the current market-load population.

Carrier pay per load requires a separate, approved quote/pricing authority that
considers the carrier, market, route, equipment, and contract. Until that tool
exists, the KB may provide approved historical earnings context but must hand
off specific rate/quote questions.

## Required view safeguards

- No load IDs, customer/facility data, raw counts, customer rates, internal
  notes, route details, or dispatch flags leave the view.
- Equipment is derived from `possible_trailer_types` only.
- The view should refresh from current data at query time or on a clearly stated
  short cadence and always return `refreshed_at`.
- Grant `SELECT` on the view only to the dedicated KB runtime role.
