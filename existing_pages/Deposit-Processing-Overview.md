# Deposit Processing Overview

**Program:** DEPOSIT.cbl
**Status:** Current
**Last reviewed:** SME-confirmed, matches code.

## Summary

The DEPOSIT program posts a deposit to an account and applies the
monthly maintenance fee waiver rule.

## Rules

1. Deposits to a **closed** account are rejected.
2. A deposit against a **dormant** account reactivates it (status set
   back to active).
3. The deposit amount is added to the account balance.
4. If the balance after the deposit is **$500.00 or more**, the
   monthly maintenance fee is waived.
5. If the balance after the deposit is **below $500.00**, a **$5.00**
   monthly maintenance fee is charged immediately.
6. Every deposit is written to the transaction log with type code
   `DP`.
