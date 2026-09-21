# Account Maintenance Field Reference

**Program:** ACCTMSTR.cbl
**Status:** Current
**Last reviewed:** 4 years ago, before the fee-code feature was added

## Summary

Reference for the fields used by the monthly ACCTMSTR batch job and
what the job does with them.

## Field notes

- `ACCT-INT-RATE` — the account's stored interest rate. Independent
  field, only used by INTCALC.
- `ACCT-FEE-CODE` — the checking-account fee code, set by ACCTMSTR.
  Independent field, unrelated to the interest rate.

## Rules

1. An account with no transaction in the last **90 days** is marked
   dormant.
2. A dormant account with no transaction in the last 365 days is
   closed.
3. If the balance is **$500.00 or more**, the monthly maintenance fee
   is waived, same threshold and comparison as DEPOSIT.
