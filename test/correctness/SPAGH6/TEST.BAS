4 TRON
5 OPEN "output" FOR OUTPUT AS 1
7 ON ERROR GOTO 1000
10 FOR I=1 TO 10
20 FOR J=100 TO 110
30 PRINT#1, I,J
40 GOTO 100
50 GOTO 100
55 RETURN
60 END
100 REM
110 NEXT
140 NEXT
999 CLOSE:END
1000 PRINT#1, "error:", ERR, ERL: PRINT ERR, ERL: RESUME NEXT

