@echo off
call "C:\Users\Public\pype_env2\Scripts\activate.bat"
setlocal enableextensions enabledelayedexpansion

set _OLD_PYTHONPATH=%PYTHONPATH%
for /d %%d in ( %~dp0repos\*) do (
echo adding path %%d
set PYTHONPATH=%%d;!PYTHONPATH!
)
pytest --ignore=%~dp0repos

set PYTHONPATH=%_OLD_PYTHONPATH%
call "C:\Users\Public\pype_env2\Scripts\deactivate.bat"
