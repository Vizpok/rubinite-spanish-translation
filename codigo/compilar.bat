@echo off
rem Genera dist\RubiniteES\ (RubiniteES.exe + carpeta _internal). Se distribuye la carpeta completa en un .zip.
rem Requiere: pip install pyinstaller UnityPy==1.25.3 TypeTreeGeneratorAPI==0.0.10 dnfile==0.18.0
cd /d "%~dp0parche"
python -m PyInstaller --noconfirm --onedir --console --noupx --name RubiniteES ^
  --version-file "%~dp0parche\version.txt" ^
  --distpath ..\dist --workpath ..\build --specpath ..\build ^
  --add-data "%~dp0parche\traduccion_es.json;." ^
  --collect-all UnityPy --collect-all TypeTreeGeneratorAPI --hidden-import dnfile instalar.py
pause
