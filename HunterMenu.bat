@echo off
TITLE Scholarships Hunter - Interactive Menu
COLOR 0A

:menu
cls
echo ==================================================
echo       SCHOLARSHIPS HUNTER - CONTROL PANEL
echo ==================================================
echo.
echo [1] Run WhatsApp Multi-Channel Live Scraper (6 Channels)
echo [2] Run Catch That Scholarship (Fast JSON)
echo [3] Run GradSchoolShopper (Fast CSV)
echo [4] Run ProFellow (Hybrid Browser/AI)
echo [5] Run WeMakeScholars (Hybrid Browser/AI)
echo [6] Run Scholarships Corner (Fast REST API)
echo [7] Run MastersPortal (Hybrid Browser/AI)
echo [8] Run Hussain Silat (Italian Public Universities Directory)
echo [9] Process Pending Backlog Queue (Ultra-Fast Groq AI)
echo [10] Run ALL Scrapers Concurrently (Async Orchestrator)
echo [11] Launch Browser for Auto-Preload and Manual Logins (All Sites + Channels)
echo [12] Clean Excel Sheet (Interactive cleaner)
echo [13] Manual Link Evaluator (Paste a URL for instant AI assessment)
echo [14] Run Deep AI Website Evaluator (Ultra-Fast 120B Model)
echo [15] Exit
echo.

set /p choice="Enter your choice (1-15): "

if "%choice%"=="1" goto whatsapp
if "%choice%"=="2" goto catch
if "%choice%"=="3" goto gss
if "%choice%"=="4" goto profellow
if "%choice%"=="5" goto wemake
if "%choice%"=="6" goto corner
if "%choice%"=="7" goto masters
if "%choice%"=="8" goto silat
if "%choice%"=="9" goto backlog
if "%choice%"=="10" goto all
if "%choice%"=="11" goto login
if "%choice%"=="12" goto clean
if "%choice%"=="13" goto manual
if "%choice%"=="14" goto deepeval
if "%choice%"=="15" goto eof

echo Invalid choice. Please try again.
pause
goto menu

:whatsapp
cls
echo Starting WhatsApp Multi-Channel Live Scraper...
echo Tracked channels: World Scholarship Opportunities, Erasmus+, Acadimia Italia, Bright Scholarship, Scholarships Corner, Fully Scholarships
set /p limit="How many recent messages per channel to sweep? (Default: 25. Use 100 for deep historical crawl): "
if "%limit%"=="" set limit=25
call .venv\Scripts\python.exe src\main.py --mode live --channel all --limit %limit%
pause
goto menu

:catch
cls
echo Starting Catch That Scholarship...
call .venv\Scripts\python.exe src\scrapers\catchthatscholarship.py
pause
goto menu

:gss
cls
echo Starting GradSchoolShopper...
call .venv\Scripts\python.exe src\scrapers\gradschoolshopper.py
pause
goto menu

:profellow
cls
echo Starting ProFellow Hybrid Scraper...
set /p pages="How many search pages would you like to sweep? (Default is 1): "
if "%pages%"=="" set pages=1
call .venv\Scripts\python.exe src\scrapers\profellow.py --pages %pages%
pause
goto menu

:wemake
cls
echo Starting WeMakeScholars Hybrid Scraper...
set /p pages="How many pages of search results would you like to sweep? (Default is 3): "
if "%pages%"=="" set pages=3
set /p cat="Discipline slug (Default: physics, e.g. applied-physics, astronomy): "
if "%cat%"=="" set cat=physics
call .venv\Scripts\python.exe src\scrapers\wemakescholars.py --pages %pages% --category %cat%
pause
goto menu

:corner
cls
echo Starting Scholarships Corner Scraper...
set /p pages="How many pages of scholarships would you like to sweep? (Default is 5): "
if "%pages%"=="" set pages=5
set /p perpage="Posts per page (Default is 50, Max 100): "
if "%perpage%"=="" set perpage=50
call .venv\Scripts\python.exe src\scrapers\scholarshipscorner.py --pages %pages% --per-page %perpage%
pause
goto menu

:masters
cls
echo Starting MastersPortal Scraper...
set /p pages="How many search pages would you like to sweep? (Default is 3): "
if "%pages%"=="" set pages=3
set /p discipline="Discipline slug (Default: physics, e.g. astronomy-space-sciences): "
if "%discipline%"=="" set discipline=physics
call .venv\Scripts\python.exe src\scrapers\mastersportal.py --pages %pages% --discipline %discipline%
pause
goto menu

:silat
cls
echo Starting Hussain Silat (Italian Public Universities Directory Scraper)...
call .venv\Scripts\python.exe src\scrapers\hussainsilat.py
pause
goto menu

:backlog
cls
echo Processing Pending Backlog Queue with Groq 120B...
call .venv\Scripts\python.exe src\main.py --mode backlog
pause
goto menu

:all
cls
echo Starting ALL Scrapers via run_all.py...
call .venv\Scripts\python.exe run_all.py
pause
goto menu

:login
cls
echo Opening Browser for manual login...
call .venv\Scripts\python.exe src\utils\manual_login.py
pause
goto menu

:clean
cls
echo Starting Excel Cleaner Utility...
call .venv\Scripts\python.exe src\utils\clean_excel.py
goto menu

:manual
cls
echo Starting Manual URL Evaluator...
call .venv\Scripts\python.exe src\utils\manual_url_evaluator.py
pause
goto menu

:deepeval
cls
echo Starting Deep AI Website Evaluator...
call .venv\Scripts\python.exe src\utils\deep_evaluator.py
pause
goto menu

:eof
exit
