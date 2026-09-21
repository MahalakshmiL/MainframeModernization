      ******************************************************************
      * PROGRAM: DEPOSIT
      * PURPOSE: POST A DEPOSIT TRANSACTION TO AN ACCOUNT AND APPLY
      *          THE MONTHLY MAINTENANCE FEE WAIVER RULE.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEPOSIT.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE ASSIGN TO ACCTMSTR
               ORGANIZATION IS INDEXED
               ACCESS IS RANDOM
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
       01  WS-DEPOSIT-AMOUNT           PIC S9(9)V99 COMP-3.
       01  WS-FEE-AMOUNT               PIC S9(9)V99 COMP-3 VALUE 5.00.
       01  WS-FEE-WAIVER-THRESHOLD     PIC S9(9)V99 COMP-3 VALUE 500.00.
       01  WS-REJECT-SWITCH            PIC X(01) VALUE 'N'.
           88  WS-REJECT               VALUE 'Y'.

       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-INITIALIZE
           PERFORM 2000-READ-ACCOUNT
           PERFORM 2100-VALIDATE-ACCOUNT
           IF NOT WS-REJECT
               PERFORM 3000-POST-DEPOSIT
               PERFORM 3100-CHECK-FEE-WAIVER
               PERFORM 4000-WRITE-TRANSACTION
           END-IF
           PERFORM 9000-TERMINATE
           STOP RUN.

       1000-INITIALIZE.
           OPEN I-O ACCOUNT-FILE
           OPEN EXTEND TRANSACTION-FILE
           MOVE 'N' TO WS-REJECT-SWITCH.

       2000-READ-ACCOUNT.
           READ ACCOUNT-FILE
               INVALID KEY
                   DISPLAY 'ACCOUNT NOT FOUND'
                   MOVE 'Y' TO WS-REJECT-SWITCH
           END-READ.

      *----------------------------------------------------------------
      * RULE: A DEPOSIT IS REJECTED IF THE ACCOUNT STATUS IS CLOSED.
      * DORMANT ACCOUNTS ARE REACTIVATED BY A DEPOSIT.
      *----------------------------------------------------------------
       2100-VALIDATE-ACCOUNT.
           IF ACCT-STATUS-CLOSED
               DISPLAY 'DEPOSIT REJECTED - ACCOUNT CLOSED'
               MOVE 'Y' TO WS-REJECT-SWITCH
           ELSE
               IF ACCT-STATUS-DORMANT
                   MOVE 'A' TO ACCT-STATUS
               END-IF
           END-IF.

      *----------------------------------------------------------------
      * RULE: THE DEPOSIT AMOUNT IS ADDED TO THE ACCOUNT BALANCE AND
      * THE LAST-TRANSACTION DATE IS REFRESHED TO TODAY.
      *----------------------------------------------------------------
       3000-POST-DEPOSIT.
           ADD WS-DEPOSIT-AMOUNT TO ACCT-BALANCE
           MOVE FUNCTION CURRENT-DATE(1:8) TO ACCT-LAST-TRAN-DATE.

      *----------------------------------------------------------------
      * RULE: IF THE RESULTING BALANCE IS $500.00 OR MORE, THE MONTHLY
      * MAINTENANCE FEE IS WAIVED FOR THIS ACCOUNT. IF THE RESULTING
      * BALANCE IS BELOW $500.00, A $5.00 MONTHLY MAINTENANCE FEE IS
      * CHARGED IMMEDIATELY AGAINST THE BALANCE.
      *----------------------------------------------------------------
       3100-CHECK-FEE-WAIVER.
           IF ACCT-BALANCE >= WS-FEE-WAIVER-THRESHOLD
               DISPLAY 'MONTHLY FEE WAIVED'
           ELSE
               SUBTRACT WS-FEE-AMOUNT FROM ACCT-BALANCE
               DISPLAY 'MONTHLY FEE CHARGED'
           END-IF.

      *----------------------------------------------------------------
      * RULE: EVERY DEPOSIT IS RECORDED IN THE TRANSACTION LOG WITH
      * TRANSACTION TYPE CODE 'DP' AND THE POST-DEPOSIT BALANCE.
      *----------------------------------------------------------------
       4000-WRITE-TRANSACTION.
           MOVE ACCT-ID TO TRAN-ACCT-ID
           MOVE 'DP' TO TRAN-TYPE
           MOVE WS-DEPOSIT-AMOUNT TO TRAN-AMOUNT
           MOVE ACCT-BALANCE TO TRAN-BALANCE-AFTER
           MOVE FUNCTION CURRENT-DATE(1:8) TO TRAN-DATE
           WRITE TRANSACTION-RECORD
           REWRITE ACCOUNT-RECORD.

       9000-TERMINATE.
           CLOSE ACCOUNT-FILE
           CLOSE TRANSACTION-FILE.
