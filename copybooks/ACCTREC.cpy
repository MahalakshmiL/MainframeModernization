      ******************************************************************
      * ACCTREC.CPY
      * ACCOUNT MASTER RECORD - DEPOSIT / ACCOUNT SERVICING MODULE
      * NOTE: ACCT-RATE-INFO IS REDEFINED. FOR SAVINGS ACCOUNTS THIS
      * STORAGE HOLDS THE INTEREST RATE. FOR CHECKING ACCOUNTS THE
      * SAME BYTES HOLD THE FEE CODE. THEY ARE THE SAME PHYSICAL
      * FIELD - A WRITE TO ONE IS A WRITE TO THE OTHER.
      ******************************************************************
       01  ACCOUNT-RECORD.
           05  ACCT-ID                     PIC X(10).
           05  ACCT-CUSTOMER-ID            PIC X(10).
           05  ACCT-TYPE                   PIC X(01).
               88  ACCT-TYPE-SAVINGS       VALUE 'S'.
               88  ACCT-TYPE-CHECKING      VALUE 'C'.
           05  ACCT-STATUS                 PIC X(01).
               88  ACCT-STATUS-ACTIVE      VALUE 'A'.
               88  ACCT-STATUS-DORMANT     VALUE 'D'.
               88  ACCT-STATUS-CLOSED      VALUE 'X'.
           05  ACCT-BALANCE                PIC S9(9)V99 COMP-3.
           05  ACCT-OPEN-DATE              PIC 9(08).
           05  ACCT-LAST-TRAN-DATE         PIC 9(08).
           05  ACCT-RATE-INFO.
               10  ACCT-INT-RATE           PIC 9(01)V9(03).
      *        USED ONLY WHEN ACCT-TYPE-SAVINGS. TIERED RATE - SEE
      *        INTCALC PARA 2200-APPLY-RATE-TIER.
           05  ACCT-RATE-INFO-R REDEFINES ACCT-RATE-INFO.
               10  ACCT-FEE-CODE           PIC X(04).
      *        USED ONLY WHEN ACCT-TYPE-CHECKING. SEE ACCTMSTR PARA
      *        3400-SET-FEE-CODE. SAME STORAGE AS ACCT-INT-RATE.
           05  ACCT-DORMANT-DAYS           PIC 9(05).
           05  FILLER                      PIC X(15).
