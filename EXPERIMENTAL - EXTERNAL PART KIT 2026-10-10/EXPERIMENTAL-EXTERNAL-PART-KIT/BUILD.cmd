@echo off
rem Builds the part described in part.json. Extra options are passed on, for example:
rem   BUILD.cmd -SkipImport                      cook what is saved in the Unreal project, without importing the model again
rem   BUILD.cmd -Retoc "C:\Tools\retoc.exe"      retoc kept somewhere else
rem   BUILD.cmd -EngineBin "D:\UE_5.6\Engine\Binaries\Win64"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Tools\Build-Part.ps1" %*
echo.
pause
