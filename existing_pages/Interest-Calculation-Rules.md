# Interest Calculation Rules

**Program:** INTCALC.cbl
**Status:** Current
**Last reviewed:** 3 years ago

## Summary

INTCALC computes and posts monthly interest for eligible accounts.

## Rules

1. Interest is calculated for savings accounts only.
2. Accounts with a balance of **$5,000.00 or more** earn a bonus
   annual rate of **4.0%**.
3. Accounts below the bonus threshold earn the account's base stored
   rate.
4. Monthly interest is balance times annual rate divided by 12.
5. Interest is posted to the account balance and logged as
   transaction type `IN`.

## Open questions

- Confirm whether dormant savings accounts should still accrue
  interest.
