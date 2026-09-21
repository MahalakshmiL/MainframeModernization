      ******************************************************************
      * TRANREC.CPY
      * TRANSACTION LOG RECORD - DEPOSIT / ACCOUNT SERVICING MODULE
      ******************************************************************
       01  TRANSACTION-RECORD.
           05  TRAN-ID                     PIC X(12).
           05  TRAN-ACCT-ID                PIC X(10).
           05  TRAN-TYPE                   PIC X(02).
               88  TRAN-TYPE-DEPOSIT       VALUE 'DP'.
               88  TRAN-TYPE-WITHDRAWAL    VALUE 'WD'.
               88  TRAN-TYPE-INTEREST      VALUE 'IN'.
               88  TRAN-TYPE-FEE           VALUE 'FE'.
           05  TRAN-AMOUNT                 PIC S9(9)V99 COMP-3.
           05  TRAN-DATE                   PIC 9(08).
           05  TRAN-BALANCE-AFTER          PIC S9(9)V99 COMP-3.
           05  TRAN-DESC                   PIC X(30).
