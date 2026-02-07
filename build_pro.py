import subprocess
import sys
import os
import shutil
import platform

def build():
    # Rilevamento piattaforma
    is_windows = platform.system() == "Windows"
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print("🚀 AVVIO MASTER BUILD IMMORTALE - SuperAgent Pro")

    # 1. Pulizia build precedenti
    for d in ["build", "dist"]:
        if os.path.exists(d):
            print(f"Pulizia cartella {d}...")
            shutil.rmtree(d)

    # 2. Creazione automatica cartelle di sistema (Evita crash al primo avvio)
    for folder in ["logs", "data", "config"]:
        os.makedirs(folder, exist_ok=True)

    # 3. Configurazione comando PyInstaller
    separator = ";" if is_windows else ":"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "main.py",               # Il file principale
        "--onefile",             # Crea un unico EXE
        "--windowed",            # Senza finestra nera del terminale
        "--name", "SuperAgent_Pro",
        "--clean",
        "--noconfirm",
        "--noupx",               # Fondamentale per evitare crash di sistema
        "--add-data", f"config{separator}config",
        "--add-data", f"data{separator}data",
    ]

    # Gestione Icona (opzionale)
    if os.path.exists("assets/icon.ico"):
        cmd.extend(["--icon", "assets/icon.ico"])

    # 4. Hidden Imports (moduli necessari per il funzionamento dell'EXE)
    hidden_imports = [
        "playwright.sync_api",
        "playwright._impl._api_types",
        "playwright._impl._api_structures",
        "psutil", 
        "yaml", 
        "requests",
        "PySide6.QtCore", 
        "PySide6.QtWidgets", 
        "PySide6.QtGui",
        "telethon"
    ]
    
    for h in hidden_imports:
        cmd.extend(["--hidden-import", h])

    # 5. Ottimizzazione Playwright & Telethon
    cmd.extend(["--collect-submodules", "playwright"])
    cmd.extend(["--collect-submodules", "telethon"])
    cmd.extend(["--exclude-module", "playwright.driver"]) # Usa il tuo Chrome locale

    print("Esecuzione compilazione in corso...")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n✅ BUILD COMPLETATA! Trovi l'eseguibile in: dist/SuperAgent_Pro.exe")
    else:
        print("\n❌ ERRORE DURANTE LA BUILD.")

if __name__ == "__main__":
    build()
