      ******************************************************************
      * PROGRAM: ACCTINQ
      * PURPOSE: READ-ONLY ACCOUNT BALANCE INQUIRY.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTINQ.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE ASSIGN TO ACCTMSTR
               ORGANIZATION IS INDEXED
               ACCESS IS RANDOM
               RECORD KEY IS ACCT-ID.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNT-FILE.
           COPY ACCTREC.

       WORKING-STORAGE SECTION.
       01  WS-NOT-FOUND-SWITCH         PIC X(01) VALUE 'N'.
           88  WS-NOT-FOUND            VALUE 'Y'.

       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-READ-ACCOUNT
           IF NOT WS-NOT-FOUND
               PERFORM 2000-DISPLAY-BALANCE
           END-IF
           PERFORM 9000-TERMINATE
           STOP RUN.

       1000-READ-ACCOUNT.
           OPEN INPUT ACCOUNT-FILE
           READ ACCOUNT-FILE
               INVALID KEY
                   DISPLAY 'ACCOUNT NOT FOUND'
                   MOVE 'Y' TO WS-NOT-FOUND-SWITCH
           END-READ.

      *----------------------------------------------------------------
      * RULE: THE INQUIRY DISPLAYS THE CURRENT BALANCE AND STATUS.
      * THIS PROGRAM PERFORMS NO UPDATES - IT IS READ-ONLY.
      *----------------------------------------------------------------
       2000-DISPLAY-BALANCE.
           DISPLAY 'ACCOUNT: ' ACCT-ID
           DISPLAY 'BALANCE: ' ACCT-BALANCE
           DISPLAY 'STATUS : ' ACCT-STATUS.

       9000-TERMINATE.
           CLOSE ACCOUNT-FILE.
