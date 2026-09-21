      ******************************************************************
      * PROGRAM: INTCALC
      * PURPOSE: MONTHLY INTEREST CALCULATION FOR SAVINGS ACCOUNTS.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INTCALC.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE ASSIGN TO ACCTMSTR
               ORGANIZATION IS INDEXED
               ACCESS IS SEQUENTIAL
               RECORD KEY IS ACCT-ID.
           SELECT TRANSACTION-FILE ASSIGN TO TRANLOG
               ORGANIZATION IS SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNT-FILE.
           COPY ACCTREC.
       FD  TRANSACTION-FILE.
           COPY TRANREC.

       WORKING-STORAGE SECTION.
       01  WS-EOF-SWITCH               PIC X(01) VALUE 'N'.
           88  WS-EOF                  VALUE 'Y'.
       01  WS-ELIGIBLE-SWITCH          PIC X(01) VALUE 'N'.
           88  WS-ELIGIBLE              VALUE 'Y'.
       01  WS-ANNUAL-RATE              PIC 9(01)V9(03).
       01  WS-BONUS-RATE               PIC 9(01)V9(03) VALUE 0.045.
       01  WS-BONUS-THRESHOLD          PIC S9(9)V99 COMP-3 VALUE 10000.00.
       01  WS-INTEREST-AMOUNT          PIC S9(9)V99 COMP-3.

       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-INITIALIZE
           PERFORM UNTIL WS-EOF
               PERFORM 2000-READ-ACCOUNT
               IF NOT WS-EOF
                   PERFORM 2100-CHECK-ELIGIBLE
                   IF WS-ELIGIBLE
                       PERFORM 2200-APPLY-RATE-TIER
                       PERFORM 2300-COMPUTE-INTEREST
                       PERFORM 3000-POST-INTEREST
                       PERFORM 4000-WRITE-TRANSACTION
                   END-IF
               END-IF
           END-PERFORM
           PERFORM 9000-TERMINATE
           STOP RUN.

       1000-INITIALIZE.
           OPEN I-O ACCOUNT-FILE
           OPEN EXTEND TRANSACTION-FILE.

       2000-READ-ACCOUNT.
           READ ACCOUNT-FILE NEXT RECORD
               AT END
                   MOVE 'Y' TO WS-EOF-SWITCH
           END-READ.

      *----------------------------------------------------------------
      * RULE: INTEREST IS CALCULATED ONLY FOR ACCOUNTS THAT ARE
      * SAVINGS TYPE AND WHOSE STATUS IS ACTIVE. CHECKING, DORMANT,
      * AND CLOSED ACCOUNTS DO NOT EARN INTEREST.
      *----------------------------------------------------------------
       2100-CHECK-ELIGIBLE.
           IF ACCT-TYPE-SAVINGS AND ACCT-STATUS-ACTIVE
               MOVE 'Y' TO WS-ELIGIBLE-SWITCH
           ELSE
               MOVE 'N' TO WS-ELIGIBLE-SWITCH
           END-IF.

      *----------------------------------------------------------------
      * RULE: ACCOUNTS WITH A BALANCE OF $10,000.00 OR MORE EARN A
      * BONUS ANNUAL INTEREST RATE OF 4.5% INSTEAD OF THE ACCOUNT'S
      * STORED RATE. ACCOUNTS BELOW $10,000.00 EARN THE RATE STORED
      * IN ACCT-INT-RATE (ONLY MEANINGFUL FOR SAVINGS ACCOUNTS - SEE
      * ACCTREC.CPY REDEFINES NOTE).
      *----------------------------------------------------------------
       2200-APPLY-RATE-TIER.
           IF ACCT-BALANCE >= WS-BONUS-THRESHOLD
               MOVE WS-BONUS-RATE TO WS-ANNUAL-RATE
           ELSE
               MOVE ACCT-INT-RATE TO WS-ANNUAL-RATE
           END-IF.

      *----------------------------------------------------------------
      * RULE: MONTHLY INTEREST = ACCOUNT BALANCE * ANNUAL RATE / 12.
      *----------------------------------------------------------------
       2300-COMPUTE-INTEREST.
           COMPUTE WS-INTEREST-AMOUNT ROUNDED =
               ACCT-BALANCE * WS-ANNUAL-RATE / 12.

      *----------------------------------------------------------------
      * RULE: INTEREST EARNED IS ADDED TO THE ACCOUNT BALANCE.
      *----------------------------------------------------------------
       3000-POST-INTEREST.
           ADD WS-INTEREST-AMOUNT TO ACCT-BALANCE
           MOVE FUNCTION CURRENT-DATE(1:8) TO ACCT-LAST-TRAN-DATE.

      *----------------------------------------------------------------
      * RULE: INTEREST POSTED IS LOGGED AS A TRANSACTION WITH TYPE
      * CODE 'IN' AND THE POST-INTEREST BALANCE.
      *----------------------------------------------------------------
       4000-WRITE-TRANSACTION.
           MOVE ACCT-ID TO TRAN-ACCT-ID
           MOVE 'IN' TO TRAN-TYPE
           MOVE WS-INTEREST-AMOUNT TO TRAN-AMOUNT
           MOVE ACCT-BALANCE TO TRAN-BALANCE-AFTER
           MOVE FUNCTION CURRENT-DATE(1:8) TO TRAN-DATE
           WRITE TRANSACTION-RECORD
           REWRITE ACCOUNT-RECORD.

       9000-TERMINATE.
           CLOSE ACCOUNT-FILE
           CLOSE TRANSACTION-FILE.
