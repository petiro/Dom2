import os
import sys

def setup_windows_task():
    print("🤖 Installazione Supervisor nel Task Scheduler di Windows...")
    
    python_exe = sys.executable
    script_path = os.path.abspath("supervisor.py")
    
    # Crea un task che parte al logon o all'avvio senza mostrare fastidiose finestre cmd
    task_name = "SuperAgent_Supervisor"
    command = f'schtasks /create /tn "{task_name}" /tr "\"{python_exe}\" \"{script_path}\"" /sc onlogon /rl highest /f'
    
    result = os.system(command)
    
    if result == 0:
        print("\n✅ INSTALLAZIONE COMPLETATA!")
        print(f"Il Supervisor ({task_name}) partirà automaticamente in background ad ogni riavvio del VPS.")
        print("Per avviarlo subito, riavvia il VPS o esegui: python supervisor.py")
    else:
        print("\n❌ Errore durante l'installazione. Assicurati di aver avviato questo script come Amministratore (eseguilo da un terminale con privilegi di Admin).")

if __name__ == "__main__":
    setup_windows_task()
