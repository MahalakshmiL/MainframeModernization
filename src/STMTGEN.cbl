      ******************************************************************
      * PROGRAM: STMTGEN
      * PURPOSE: GENERATE A PRINTED ACCOUNT STATEMENT FROM THE
      *          TRANSACTION LOG.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. STMTGEN.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE ASSIGN TO ACCTMSTR
               ORGANIZATION IS INDEXED
               ACCESS IS SEQUENTIAL
               RECORD KEY IS ACCT-ID.
           SELECT TRANSACTION-FILE ASSIGN TO TRANLOG
               ORGANIZATION IS SEQUENTIAL.
           SELECT STATEMENT-FILE ASSIGN TO STMTOUT
               ORGANIZATION IS SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNT-FILE.
           COPY ACCTREC.
       FD  TRANSACTION-FILE.
           COPY TRANREC.
       FD  STATEMENT-FILE.
       01  STMT-LINE                   PIC X(80).

       WORKING-STORAGE SECTION.
       01  WS-EOF-SWITCH               PIC X(01) VALUE 'N'.
           88  WS-EOF                  VALUE 'Y'.
       01  WS-TRAN-EOF-SWITCH          PIC X(01) VALUE 'N'.
           88  WS-TRAN-EOF             VALUE 'Y'.

       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-OPEN-FILES
           PERFORM UNTIL WS-EOF
               PERFORM 2000-READ-ACCOUNT
               IF NOT WS-EOF
                   PERFORM 3000-PRINT-HEADER
                   PERFORM 4000-PRINT-TRANSACTIONS
                   PERFORM 5000-UPDATE-LAST-STMT-DATE
               END-IF
           END-PERFORM
           PERFORM 9000-TERMINATE
           STOP RUN.

       1000-OPEN-FILES.
           OPEN INPUT ACCOUNT-FILE
           OPEN INPUT TRANSACTION-FILE
           OPEN OUTPUT STATEMENT-FILE.

       2000-READ-ACCOUNT.
           READ ACCOUNT-FILE NEXT RECORD
               AT END
                   MOVE 'Y' TO WS-EOF-SWITCH
           END-READ.

      *----------------------------------------------------------------
      * RULE: EACH STATEMENT PAGE STARTS WITH THE ACCOUNT ID, TYPE,
      * AND CURRENT BALANCE.
      *----------------------------------------------------------------
       3000-PRINT-HEADER.
           MOVE SPACES TO STMT-LINE
           STRING 'ACCOUNT ' ACCT-ID ' BALANCE ' ACCT-BALANCE
               DELIMITED BY SIZE INTO STMT-LINE
           WRITE STMT-LINE.

       4000-PRINT-TRANSACTIONS.
           MOVE 'N' TO WS-TRAN-EOF-SWITCH
           PERFORM UNTIL WS-TRAN-EOF
               READ TRANSACTION-FILE NEXT RECORD
                   AT END
                       MOVE 'Y' TO WS-TRAN-EOF-SWITCH
               END-READ
               IF NOT WS-TRAN-EOF AND TRAN-ACCT-ID = ACCT-ID
                   MOVE SPACES TO STMT-LINE
                   STRING TRAN-TYPE ' ' TRAN-AMOUNT ' ' TRAN-DATE
                       DELIMITED BY SIZE INTO STMT-LINE
                   WRITE STMT-LINE
               END-IF
           END-PERFORM.

      *----------------------------------------------------------------
      * RULE: PRODUCING A STATEMENT REFRESHES THE ACCOUNT'S LAST
      * ACTIVITY DATE, WHICH PREVENTS THE ACCOUNT FROM BEING MARKED
      * DORMANT BY ACCTMSTR SOLELY BECAUSE NO CUSTOMER TRANSACTION
      * OCCURRED THIS CYCLE.
      *----------------------------------------------------------------
       5000-UPDATE-LAST-STMT-DATE.
           MOVE FUNCTION CURRENT-DATE(1:8) TO ACCT-LAST-TRAN-DATE.

       9000-TERMINATE.
           CLOSE ACCOUNT-FILE
           CLOSE TRANSACTION-FILE
           CLOSE STATEMENT-FILE.
