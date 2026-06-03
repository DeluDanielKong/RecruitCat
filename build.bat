@echo off
chcp 65001 > nul
echo ============================================================
echo   招聘猫 - 打包脚本
echo ============================================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 安装依赖
echo [1/3] 安装依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

pip install pyinstaller
if errorlevel 1 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)

echo.
echo [1.5/3] 移除与 PyInstaller 不兼容的旧版 pathlib 包...
conda remove --force pathlib -y 2>nul || pip uninstall pathlib -y 2>nul
echo.
echo [2/3] 开始打包...
echo.

:: 打包命令
::   --onefile       : 打包为单个 exe
::   --windowed      : 不显示命令行窗口
::   --name          : exe 名称
::   --add-data      : 附带额外文件（如有图标）
::   --hidden-import : 手动声明隐式依赖

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "招聘猫" ^
  --hidden-import=bs4 ^
  --hidden-import=lxml ^
  --hidden-import=lxml.etree ^
  --hidden-import=openpyxl ^
  --hidden-import=requests ^
  --hidden-import=urllib3 ^
  --collect-submodules=bs4 ^
  --collect-submodules=lxml ^
  main.py

if errorlevel 1 (
    echo [错误] 打包失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo [3/3] 打包完成！
echo.
echo exe 文件位于：dist\招聘猫.exe
echo.

:: 复制示例网站文件到 dist\
if exist "示例网站.txt" (
    copy "示例网站.txt" "dist\示例网站.txt" >nul
    echo 已将示例网站.txt 复制到 dist\ 目录
)

echo.
echo 按任意键打开 dist 目录...
pause >nul
start dist
