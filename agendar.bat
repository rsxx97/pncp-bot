@echo off
schtasks /create /tn "PNCP Bot" /tr "\"C:\Users\Bruno Campos\AppData\Local\Programs\Python\Python314\python.exe\" \"C:\Users\Bruno Campos\Desktop\Nova pasta\pncp_telegram_bot.py\"" /sc daily /st 11:00 /f
pause
