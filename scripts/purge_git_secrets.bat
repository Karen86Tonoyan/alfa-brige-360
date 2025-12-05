@echo off
REM =====================================================
REM ALFA PURGE - Usuwa wrażliwe pliki z historii Git
REM Uruchom TYLKO jeśli klucz API był commitowany!
REM =====================================================

echo.
echo [ALFA PURGE] Czyszczenie historii Git z wrazliwych plikow...
echo.
echo UWAGA: Ta operacja jest NIEODWRACALNA!
echo Przed kontynuacja zrob backup repozytorium.
echo.

set /p confirm="Czy chcesz kontynuowac? (tak/nie): "
if /i not "%confirm%"=="tak" (
    echo [ANULOWANO] Operacja przerwana przez uzytkownika.
    exit /b 0
)

echo.
echo [KROK 1] Instalacja git-filter-repo (jesli brak)...
pip install git-filter-repo 2>nul

echo.
echo [KROK 2] Usuwanie .env z historii...
git filter-repo --invert-paths --path .env --force 2>nul || (
    echo [INFO] git-filter-repo niedostepny, uzywam filter-branch...
    git filter-branch --force --index-filter "git rm --cached --ignore-unmatch .env" --prune-empty --tag-name-filter cat -- --all
)

echo.
echo [KROK 3] Usuwanie master.key z historii...
git filter-repo --invert-paths --path "**/master.key" --force 2>nul || (
    git filter-branch --force --index-filter "git rm --cached --ignore-unmatch **/master.key" --prune-empty --tag-name-filter cat -- --all
)

echo.
echo [KROK 4] Usuwanie secrets.enc z historii...
git filter-repo --invert-paths --path "**/secrets.enc" --force 2>nul || (
    git filter-branch --force --index-filter "git rm --cached --ignore-unmatch **/secrets.enc" --prune-empty --tag-name-filter cat -- --all
)

echo.
echo [KROK 5] Czyszczenie reflog i gc...
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo.
echo =====================================================
echo [ALFA PURGE] GOTOWE!
echo.
echo WAZNE: Teraz musisz:
echo   1. git push --force --all
echo   2. Wygenerowac NOWE klucze API (stare sa skompromitowane)
echo   3. Zapisac nowe klucze w SecretStore
echo =====================================================
echo.

pause
