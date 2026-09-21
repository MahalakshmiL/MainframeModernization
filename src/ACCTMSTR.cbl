      ******************************************************************
      * PROGRAM: ACCTMSTR
      * PURPOSE: MONTHLY BATCH ACCOUNT MAINTENANCE - DORMANCY CHECK,
      *          ACCOUNT CLOSURE, FEE CODE ASSIGNMENT, MONTHLY FEE
      *          PROCESSING, AND CONTROL TOTALS.
      * NOTE: THIS IS THE LARGEST PROGRAM IN THE MODULE.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTMSTR.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE ASSIGN TO ACCTMSTR
               ORGANIZATION IS INDEXED
               ACCESS IS SEQUENTIAL
               RECORD KEY IS ACCT-ID.
           SELECT TRANSACTION-FILE ASSIGN TO TRANLOG
               ORGANIZATION IS SEQUENTIAL.
           SELECT CONTROL-REPORT ASSIGN TO CTLRPT
               ORGANIZATION IS SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNT-FILE.
           COPY ACCTREC.
       FD  TRANSACTION-FILE.
           COPY TRANREC.
       FD  CONTROL-REPORT.
       01  CTL-LINE                    PIC X(80).

       WORKING-STORAGE SECTION.
       01  WS-EOF-SWITCH               PIC X(01) VALUE 'N'.
           88  WS-EOF                  VALUE 'Y'.
       01  WS-TODAY                    PIC 9(08).
       01  WS-DAYS-SINCE-LAST-TRAN     PIC 9(05).
       01  WS-DORMANT-THRESHOLD        PIC 9(05) VALUE 180.
       01  WS-CLOSE-THRESHOLD          PIC 9(05) VALUE 365.
       01  WS-FEE-AMOUNT               PIC S9(9)V99 COMP-3 VALUE 5.00.
      *----------------------------------------------------------------
      * NOTE: THIS THRESHOLD IS THE SAME $500.00 FIGURE USED IN
      * DEPOSIT PARA 3100-CHECK-FEE-WAIVER, BUT THE COMPARISON BELOW
      * IN 4100-CHECK-FEE-WAIVER-MSTR USES STRICTLY-GREATER-THAN
      * WHILE DEPOSIT USES GREATER-THAN-OR-EQUAL. AN ACCOUNT SITTING
      * AT EXACTLY $500.00 IS WAIVED BY DEPOSIT BUT CHARGED BY THIS
      * BATCH JOB.
      *----------------------------------------------------------------
       01  WS-FEE-WAIVER-THRESHOLD     PIC S9(9)V99 COMP-3 VALUE 500.00.
       01  WS-DORMANT-COUNT            PIC 9(07) VALUE ZERO.
       01  WS-CLOSED-COUNT             PIC 9(07) VALUE ZERO.
       01  WS-FEE-COUNT                PIC 9(07) VALUE ZERO.
       01  WS-ACCOUNTS-PROCESSED       PIC 9(07) VALUE ZERO.
       01  WS-OD-SWITCH                PIC X(01) VALUE 'N'.
           88  WS-OVERDRAWN            VALUE 'Y'.

       PROCEDURE DIVISION.
       0000-MAIN-CONTROL.
           PERFORM 1000-INITIALIZE
           PERFORM 1100-OPEN-FILES
           PERFORM 2000-PROCESS-ACCOUNTS UNTIL WS-EOF
           PERFORM 7000-PRODUCE-CONTROL-TOTALS
           PERFORM 9000-TERMINATE
           STOP RUN.

       1000-INITIALIZE.
           MOVE FUNCTION CURRENT-DATE(1:8) TO WS-TODAY.

       1100-OPEN-FILES.
           OPEN I-O ACCOUNT-FILE
           OPEN EXTEND TRANSACTION-FILE
           OPEN OUTPUT CONTROL-REPORT.

       2000-PROCESS-ACCOUNTS.
           PERFORM 2100-READ-NEXT-ACCOUNT
           IF NOT WS-EOF
               PERFORM 2200-VALIDATE-ACCOUNT-TYPE
               PERFORM 3000-DORMANCY-CHECK
               PERFORM 3400-SET-FEE-CODE
               PERFORM 4000-MONTHLY-FEE-PROCESSING
               PERFORM 5000-REBUILD-INDEX-FLAGS
               PERFORM 6000-WRITE-ACCOUNT-RECORD
               ADD 1 TO WS-ACCOUNTS-PROCESSED
           END-IF.

       2100-READ-NEXT-ACCOUNT.
           READ ACCOUNT-FILE NEXT RECORD
               AT END
                   MOVE 'Y' TO WS-EOF-SWITCH
           END-READ.

      *----------------------------------------------------------------
      * RULE: ONLY SAVINGS ('S') AND CHECKING ('C') ACCOUNT TYPES ARE
      * RECOGNIZED. ANY OTHER VALUE IS LOGGED AS A DATA EXCEPTION BUT
      * PROCESSING CONTINUES.
      *----------------------------------------------------------------
       2200-VALIDATE-ACCOUNT-TYPE.
           IF NOT ACCT-TYPE-SAVINGS AND NOT ACCT-TYPE-CHECKING
               DISPLAY 'DATA EXCEPTION - UNKNOWN ACCT TYPE ' ACCT-ID
           END-IF.

       3000-DORMANCY-CHECK.
           PERFORM 3100-CALC-DAYS-SINCE-LAST-TRAN
           IF ACCT-STATUS-ACTIVE
               PERFORM 3200-MARK-DORMANT
           END-IF
           IF ACCT-STATUS-DORMANT
               PERFORM 3300-CLOSE-LONG-DORMANT
           END-IF.

       3100-CALC-DAYS-SINCE-LAST-TRAN.
           COMPUTE WS-DAYS-SINCE-LAST-TRAN =
               FUNCTION INTEGER-OF-DATE(WS-TODAY) -
               FUNCTION INTEGER-OF-DATE(ACCT-LAST-TRAN-DATE).

      *----------------------------------------------------------------
      * RULE: AN ACTIVE ACCOUNT WITH NO TRANSACTION FOR MORE THAN 180
      * DAYS IS MARKED DORMANT.
      *----------------------------------------------------------------
       3200-MARK-DORMANT.
           IF WS-DAYS-SINCE-LAST-TRAN > WS-DORMANT-THRESHOLD
               MOVE 'D' TO ACCT-STATUS
               ADD 1 TO WS-DORMANT-COUNT
           END-IF.

      *----------------------------------------------------------------
      * RULE: A DORMANT ACCOUNT WITH NO TRANSACTION FOR MORE THAN 365
      * DAYS IS CLOSED BY THE SYSTEM.
      *----------------------------------------------------------------
       3300-CLOSE-LONG-DORMANT.
           IF WS-DAYS-SINCE-LAST-TRAN > WS-CLOSE-THRESHOLD
               MOVE 'X' TO ACCT-STATUS
               ADD 1 TO WS-CLOSED-COUNT
           END-IF.

      *----------------------------------------------------------------
      * RULE: FOR CHECKING ACCOUNTS ONLY, THE FEE CODE IS SET BASED
      * ON THE CURRENT BALANCE. THIS WRITES ACCT-FEE-CODE, WHICH
      * PHYSICALLY OVERLAPS ACCT-INT-RATE (SEE ACCTREC.CPY REDEFINES).
      * SAVINGS ACCOUNTS MUST NEVER REACH THIS PARAGRAPH'S MOVE
      * BECAUSE IT WOULD OVERWRITE THE STORED INTEREST RATE.
      *----------------------------------------------------------------
       3400-SET-FEE-CODE.
           IF ACCT-TYPE-CHECKING
               IF ACCT-BALANCE < ZERO
                   MOVE 'ODFE' TO ACCT-FEE-CODE
               ELSE
                   MOVE 'STD ' TO ACCT-FEE-CODE
               END-IF
           END-IF.

       4000-MONTHLY-FEE-PROCESSING.
           IF ACCT-STATUS-ACTIVE
               PERFORM 4100-CHECK-FEE-WAIVER-MSTR
           END-IF.

      *----------------------------------------------------------------
      * RULE: IF THE BALANCE IS GREATER THAN $500.00 THE MONTHLY
      * MAINTENANCE FEE IS WAIVED. OTHERWISE THE FEE IS APPLIED.
      * NOTE THE BOUNDARY: THIS CHECK IS STRICTLY-GREATER-THAN, NOT
      * GREATER-THAN-OR-EQUAL.
      *----------------------------------------------------------------
       4100-CHECK-FEE-WAIVER-MSTR.
           IF ACCT-BALANCE > WS-FEE-WAIVER-THRESHOLD
               DISPLAY 'MONTHLY FEE WAIVED - BATCH'
           ELSE
               PERFORM 4200-APPLY-MONTHLY-FEE
               PERFORM 4300-WRITE-FEE-TRANSACTION
           END-IF.

       4200-APPLY-MONTHLY-FEE.
           SUBTRACT WS-FEE-AMOUNT FROM ACCT-BALANCE
           ADD 1 TO WS-FEE-COUNT.

       4300-WRITE-FEE-TRANSACTION.
           MOVE ACCT-ID TO TRAN-ACCT-ID
           MOVE 'FE' TO TRAN-TYPE
           MOVE WS-FEE-AMOUNT TO TRAN-AMOUNT
           MOVE ACCT-BALANCE TO TRAN-BALANCE-AFTER
           MOVE WS-TODAY TO TRAN-DATE
           WRITE TRANSACTION-RECORD.

      *----------------------------------------------------------------
      * DEAD CODE: NOT PERFORMED FROM ANYWHERE IN THIS PROGRAM. THIS
      * WAS THE ORIGINAL OVERDRAFT CHARGE RULE, SUPERSEDED WHEN
      * WITHDRWL PARA 2200-VALIDATE-FUNDS STARTED BLOCKING OVERDRAWN
      * WITHDRAWALS IN REAL TIME. LEFT IN SOURCE, NEVER REMOVED.
      * A $35.00 OVERDRAFT CHARGE ON A NEGATIVE BALANCE IS NOT LIVE
      * BUSINESS LOGIC AND MUST NOT BE REPORTED AS A CURRENT RULE.
      *----------------------------------------------------------------
       4700-LEGACY-OVERDRAFT-CHARGE.
           IF ACCT-BALANCE < ZERO
               MOVE 'Y' TO WS-OD-SWITCH
               SUBTRACT 35.00 FROM ACCT-BALANCE
           END-IF.

      *----------------------------------------------------------------
      * DEAD CODE: COMPANION TO 4700-LEGACY-OVERDRAFT-CHARGE, ALSO
      * NEVER PERFORMED. KEPT FOR THE SAME REASON.
      *----------------------------------------------------------------
       4750-LEGACY-OVERDRAFT-NOTIFY.
           IF WS-OVERDRAWN
               DISPLAY 'OVERDRAFT CHARGE APPLIED - LEGACY PATH'
           END-IF.

       5000-REBUILD-INDEX-FLAGS.
           PERFORM 5100-UPDATE-DORMANT-COUNTER.

       5100-UPDATE-DORMANT-COUNTER.
           MOVE WS-DAYS-SINCE-LAST-TRAN TO ACCT-DORMANT-DAYS.

       6000-WRITE-ACCOUNT-RECORD.
           REWRITE ACCOUNT-RECORD.

       7000-PRODUCE-CONTROL-TOTALS.
           MOVE SPACES TO CTL-LINE
           STRING 'ACCOUNTS PROCESSED: ' WS-ACCOUNTS-PROCESSED
               DELIMITED BY SIZE INTO CTL-LINE
           WRITE CTL-LINE
           MOVE SPACES TO CTL-LINE
           STRING 'MARKED DORMANT: ' WS-DORMANT-COUNT
               DELIMITED BY SIZE INTO CTL-LINE
           WRITE CTL-LINE
           MOVE SPACES TO CTL-LINE
           STRING 'CLOSED: ' WS-CLOSED-COUNT
               DELIMITED BY SIZE INTO CTL-LINE
           WRITE CTL-LINE
           MOVE SPACES TO CTL-LINE
           STRING 'FEES CHARGED: ' WS-FEE-COUNT
               DELIMITED BY SIZE INTO CTL-LINE
           WRITE CTL-LINE.

       9000-TERMINATE.
           CLOSE ACCOUNT-FILE
           CLOSE TRANSACTION-FILE
           CLOSE CONTROL-REPORT.
