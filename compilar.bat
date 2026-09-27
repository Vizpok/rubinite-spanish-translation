@echo off
rem Genera dist\RubiniteES.exe (requiere: pip install pyinstaller UnityPy==1.25.3 TypeTreeGeneratorAPI==0.0.10 dnfile==0.18.0)
cd /d "%~dp0parche"
python -m PyInstaller --noconfirm --onefile --console --name RubiniteES --distpath ..\dist --workpath ..uild --specpath ..uild --add-data "%~dp0parche	raduccion_es.json;." --collect-all UnityPy --collect-all TypeTreeGeneratorAPI --hidden-import dnfile instalar.py
pause
