@echo off
setlocal
if exist "%~dp0..\.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0..\.env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)
py -3 "%~dp0fetch_pmids.py" %*
