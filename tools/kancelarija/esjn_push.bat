@echo off
setlocal
REM ESJN (Makedonija) - preuzmi i gurni u repozitorij. Pokrece se na kancelarijskom
REM racunaru (Windows) na OBICNOJ vezi, jednom dnevno, iz Task Schedulera.
REM Prije prvog pokretanja:
REM   1) git clone https://github.com/fullvedo-del/tender-radar.git C:\tender-radar
REM   2) postavi varijable okruzenja GH_TOKEN (GitHub token, pravo contents: write) i REPO_DIR.
REM Token NIJE u kodu; cita se iz okruzenja.

if "%REPO_DIR%"=="" set REPO_DIR=C:\tender-radar
if "%GH_TOKEN%"=="" (echo GH_TOKEN nije postavljen & exit /b 1)

cd /d "%REPO_DIR%" || exit /b 1
git pull --rebase --quiet || exit /b 1
python tools\esjn_fetch.py data\esjn_raw.json || exit /b 1
git add data\esjn_raw.json
git diff --cached --quiet && (echo Nema promjena & exit /b 0)
git commit -m "ESJN: makedonske nabavke (auto %date%)" || exit /b 1
git pull --rebase --quiet
git push https://%GH_TOKEN%@github.com/fullvedo-del/tender-radar.git HEAD:main
endlocal
