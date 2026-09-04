# Market earnings data contract

## Purpose

Provide carrier-facing, aggregate market context without exposing individual
driver, carrier, customer, load, facility, or settlement records.

This is a live-data contract, not a retrieval document. The production KB will
call a migration-owned, read-only projection rather than query LoHi tables
directly.

## Candidate v1 metric

`median_base_gross_per_full_shift_cents` is the median of each eligible
driver's average base gross pay per qualified shift in a market during the
trailing 28 days.

Base gross includes only load-linked settled line items with these descriptions:

- Line Haul
- Deadhead
- Fuel Surcharge
- Bonus and Bonus Boost when directly attached to a load
- Truck Ordered Not Used (TONU)
- Detention, Loading Detention, and Unloading Detention

The public response must include the window, driver count, qualified-shift
count, settlement coverage, and `refreshed_at`. It should lead with the median,
not a maximum or top-earner value.

## Explicit exclusions

- Individual driver/carrier identity, earnings, routes, or facility history.
- Unsettled amounts, raw rate cards, customer margins, and internal notes.
- Fees, deposits, tier take rates, trailer charges, and taxes. These belong in
  a separately approved commercial-policy answer, not an earnings claim.
- Driver-linked `settlement_statement_item` adjustments until their attribution
  to an individual market and shift is reviewed.

The historical reference workbook includes ad-hoc bonuses. In the Jul 5–Aug 1
validation window, 559 bonus items had one candidate shift in the approved
market set, while 1,288 had two or more candidates. Guessing an allocation
would distort market comparisons, so v1 deliberately excludes those ambiguous
bonuses and calls the metric **base gross**.

## Eligibility and disclosure controls

- A full shift is over 10 hours and has either at least three completed loads
  or at least 175 usable miles.
- Miles use `vpf.load_distance_event` categories 4 and 5 and are discarded
  when they exceed `hours * 75` mph.
- Suppress a market when fewer than 10 eligible drivers are represented.
- Return a low-sample flag when 10–19 drivers are represented.
- Do not claim current opportunity or load availability from historical
  earnings. That requires a separate, live availability contract.

## Validation status

The source path is confirmed:

```text
vpf.shift → vpf.load_shift → lohiloop_load → settlement_statement_load
          → settlement_statement_load_line_item
```

`vpf.autodispatch_pool.external_title` supplies the market label. The initial
reconstruction found 3,237 qualified shifts in the workbook's historical
market set versus 3,082 in the reference workbook. Base components reconciled
closely, but this five-percent population difference must be explained before
creating a production view. Likely causes include post-report data changes or
the reference report's shift-selection logic.

## Production acceptance criteria

1. The report owner confirms the full-shift selection and market mapping.
2. The view reproduces the reference workbook within an agreed tolerance for a
   frozen window.
3. A source owner approves the public wording: it must say "typical base gross
   per qualified shift," not "guaranteed earnings."
4. The view is granted to the KB runtime role; it exposes aggregates only.
