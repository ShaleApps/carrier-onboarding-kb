# LoHi market-view provisioning

## Decision required from market owner

Approve the following carrier-public disclosures:

1. Market name and timezone.
2. Aggregate recent and 90-day completed-load counts, clearly labeled as
   historical activity rather than availability.
3. Facility name, city, and state only when the facility has at least ten
   completed loads in the trailing 90 days.
4. Aggregate trailer-type counts over the trailing 28 days.

Do **not** approve facility address, contact information, notes, appointment
details, customer margin/rate data, raw loads, or historical lane pairs at this
time. Lane disclosure needs a separate decision.

## DBA request

After approval, create a migration-owned view named:

```text
carrier_kb_public_market_catalog_v1
```

Use the query in `docs/market-catalog-prototype.sql` as its definition, binding:

```text
:recent_start  = now() - interval '28 days'
:history_start = now() - interval '90 days'
```

The view must expose exactly these columns:

```text
market_id
market_name
timezone
recent_load_count
completed_load_count_90d
last_completed_load_at
facilities
equipment
refreshed_at
```

`facilities` and `equipment` are JSON arrays using the shapes in
`docs/market-catalog-data-contract.md`. Do not add source-table IDs beyond the
market/facility IDs already required by the contract, driver/carrier identity,
or raw load fields.

Grant only the view to the KB runtime role:

```sql
GRANT SELECT ON carrier_kb_public_market_catalog_v1 TO carrier_kb_runtime;
```

Replace `carrier_kb_runtime` with the actual staging/production runtime role.
Do not grant the KB role direct access to `lohiloop_load`, `vpf.shift`,
`settlement_statement*`, or `tour_customer.facility`.

## KB activation

After the view and grant are deployed, configure the runtime secret:

```text
LOHI_READ_DSN=<read-only KB role DSN>
LOHI_MARKET_CATALOG_VIEW=carrier_kb_public_market_catalog_v1
LOHI_MARKET_OPPORTUNITY_VIEW=carrier_kb_public_market_opportunity_v1
```

Each client remains disabled until its view variable is configured. They use an
exact case-insensitive market-name match; an ambiguous view result fails closed.

## Current opportunity view

The same owner/DBA process can provision:

```text
carrier_kb_public_market_opportunity_v1
```

Use `docs/market-opportunity-prototype.sql` as the definition. It exposes only
market name, a coarse `none`/`limited`/`active` availability band, aggregate
equipment, and `refreshed_at`. It must not expose raw load counts, individual
loads, lanes, facilities, customer rates, or carrier-pay quotes.

```sql
GRANT SELECT ON carrier_kb_public_market_opportunity_v1 TO carrier_kb_runtime;
```

## Earnings view remains pending

Do not create `carrier_kb_public_market_earnings_v1` yet. It requires the
earnings report owner to reconcile the five-percent shift-population difference
and approve the public wording for the conservative base-gross metric. The
candidate definition is in `docs/market-earnings-data-contract.md`.
