@echo off
REM Wrapper pour exécuter scripts\curl_avg.ps1 depuis CMD
SET PS1=%~dp0curl_avg.ps1
IF NOT EXIST "%PS1%" (
  echo Script introuvable: %PS1%
  exit /b 1
)

REM Usage: curl_avg.bat [count] [url]
IF "%1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
) ELSE IF "%2"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Count %1
) ELSE (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Count %1 -Url "%2"
)
