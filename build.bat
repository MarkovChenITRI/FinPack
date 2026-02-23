@echo off
chcp 65001 >nul
echo ========================================
echo   FinPack 打包腳本
echo ========================================
echo.

:: 檢查 Python 是否安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python
    pause
    exit /b 1
)

echo.
echo [1/5] 清理舊的打包檔案...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "build_venv" rmdir /s /q build_venv

echo.
echo [2/5] 建立乾淨的虛擬環境...
python -m venv build_venv
call build_venv\Scripts\activate.bat

echo.
echo [3/5] 安裝 requirements.txt 套件...
build_venv\Scripts\python.exe -m pip install --upgrade pip
build_venv\Scripts\pip.exe install flask yfinance pandas numpy scipy scikit-learn requests pyinstaller

echo.
echo [4/5] 開始打包（這可能需要幾分鐘）...
build_venv\Scripts\pyinstaller.exe finpack.spec --noconfirm

echo.
echo [5/5] 建立快取資料夾...
if not exist "dist\FinPack\cache" mkdir "dist\FinPack\cache"

:: 關閉虛擬環境
call deactivate

echo.
echo ========================================
echo   打包完成！
echo ========================================
echo.
echo 輸出位置: dist\FinPack\
echo 執行檔案: dist\FinPack\FinPack.exe
echo.
echo 將整個 FinPack 資料夾複製到其他電腦即可使用
echo.
pause
