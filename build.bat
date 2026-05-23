@echo off
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name inject --distpath dist --workpath build --clean inject.py
echo.
echo Build complete! Output: dist\inject.exe
echo Don't forget to place inject.txt next to inject.exe
pause
