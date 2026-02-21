```markdown
🤖 SuperAgent - Trading Automation OS (V8.5 Hedge-Grade)

SuperAgent non è un semplice script o un "bot Python", ma un Sistema Operativo di Automazione Finanziaria (Trading OS) progettato per operare in autonomia totale 24/7 su VPS/Server Dedicati.

È strutturato per intercettare segnali da Telegram, analizzarli tramite AI, mappare i selettori DOM e piazzare scommesse sportive in modo totalmente invisibile ai sistemi anti-frode (Datadome, Akamai), garantendo un uptime del 100% grazie al suo strato di supervisione OS e prevenendo qualsiasi perdita di dati.

---

### 📂 Struttura del Repository

Ecco l'elenco completo di tutti i file attualmente caricati e disponibili nell'ambiente (estratti dal repository `dom2` e dai tuoi caricamenti recenti):

**Directory Principale / Root (`petiro/dom2/Dom2-.../`):**

* `.gitignore`
* `AUDIT_REPORT.md`
* `README.md`
* `hedge_super_tester.py`
* `main.py`
* `pyproject.toml`
* `quant_ci_evaluator.py`
* `repo_audit.py`
* `requirements.txt`
* `setup_vps_task.py`
* `supervisor.py`
* `tester_v4.py`

**Directory `.github/workflows/`:**

* `build.yml`
* `openrouter_audit.yml`
* `production_check.yml`
* `v4_test_suite.yml`
* `v7_quant_monitoring.yml`

**Directory `config/`:**

* `config.yaml`
* `robots.yaml`
* `selectors.yaml`

**Directory `core/`:**

* `ai_parser.py`
* `ai_selector_validator.py`
* `ai_trainer.py`
* `anti_detect.py`
* `arch_v6.py`
* `auto_mapper_worker.py`
* `bet_worker.py`
* `command_parser.py`
* `config_loader.py`
* `config_paths.py`
* `controller.py`
* `crypto_vault.py`
* `database.py`
* `dom_executor_playwright.py`
* `dom_self_healing.py`
* `event_bus.py`
* `events.py`
* `execution_engine.py`
* `geometry.py`
* `health.py`
* `heartbeat.py`
* `human_behavior.py`
* `human_mouse.py`
* `lifecycle.py`
* `logger.py`
* `money_management.py`
* `multi_site_scanner.py`
* `os_human_interaction.py`
* `playwright_worker.py`
* `secure_storage.py`
* `security.py`
* `security_logger.py`
* `signal_parser.py`
* `state_machine.py`
* `telegram_worker.py`
* `utils.py`

**Directory `data/`:**

* `chrome_icon.png`

**Directory `tests/`:**

* `stress_lab/GOD_MODE_chaos.py`
* `stress_lab/mock_executor.py`
* `stress_lab/quant_monitor.py`
* `stress_lab/stability_metrics.py`
* `stress_lab/super_tester_v7.py`
* `stress_lab/tests/__init__.py`
* `stress_lab/tests/tests/stress_lab/__init__.py`
* `tests/system_integrity/ENDURANCE_TEST.py`
* `tests/system_integrity/ULTRA_SYSTEM_TEST.py`

**Directory `ui/`:**

* `bookmaker_tab.py`
* `desktop_app.py`
* `robots_tab.py`
* `selectors_tab.py`

---

### 🖥️ Interfaccia Grafica (GUI) - SUPERAGENT OS

L'interfaccia è suddivisa in 6 sezioni principali (Tab), progettate per una gestione sicura e intuitiva:

#### 1. 📊 Dashboard
La schermata iniziale di benvenuto e stato del sistema.
* **Contenuto Visivo:** Mostra il messaggio di stato "SYSTEM STATUS: 🟢 WATCHDOG OS ACTIVE".
* **Funzionalità:** Avvisa l'utente che tutti i dati sono protetti nel Vault sicuro situato in `~/.superagent_data/` e che il backup automatico è attivo.

#### 2. 💰 Bookmakers
Questa è la tua cassaforte per le credenziali.
* **Pannello di Sinistra (Lista):** Mostra l'elenco dei bookmaker salvati, visualizzando il Nome e lo Username, ma mantenendo la password nascosta per sicurezza.
    * 🔘 **Pulsante `❌ Elimina Selezionato`:** Il sistema identifica l'ID o il nome del bookmaker, chiede al `secure_storage` di rimuovere la chiave crittografata corrispondente e aggiorna la lista visiva a sinistra.
* **Pannello di Destra (Aggiunta):** Form per inserire un nuovo account con i campi di testo `Nome Bookmaker` (es. Bet365_Principale), `Username` e `Password` (oscurata in fase di digitazione).
    * 🔘 **Pulsante `➕ Salva Bookmaker`:** Il file della UI preleva i testi e chiama il modulo `core.secure_storage`. La password *non viene mai salvata in chiaro*. Viene crittografata usando una chiave generata specificamente per la tua macchina e salvata in un file binario/sicuro. I campi si svuotano, la UI si aggiorna in tempo reale e appare un popup di conferma.

#### 3. 🧩 Selettori
Qui insegni al bot come "vedere" il sito web (dove cliccare, dove leggere le quote).
* **Pannello di Sinistra (Lista):** Mostra tutti i selettori salvati formattati come "Nome | Bookmaker | Valore CSS/XPath".
    * 🔘 **Pulsante `❌ Elimina Selezionato`:** Puoi eliminare selettori vecchi se il bookmaker cambia grafica. L'eliminazione riscrive il file YAML mantenendolo pulito e leggero.
* **Pannello di Destra (Aggiunta):** Form per istruire il bot, con i campi `Nome selettore` (es. tasto_scommetti), `Bookmaker target` e `Valore (CSS/XPath)`.
    * 🔘 **Pulsante `➕ Salva Selettore`:** Il bot prende questi dati e aggiorna fisicamente il file `config/selectors.yaml`. Quando il `PlaywrightWorker` navigherà su Bet365, aprirà questo file in memoria per sapere esattamente su quale elemento HTML fare click.

#### 4. 🤖 Robot & Strategie
Questo è il centro di comando tattico. È la tab più intelligente dell'interfaccia.
* **Pannello di Sinistra (Lista):** Visualizza i Robot attivi e mostra a quale ID account Bookmaker sono assegnati. Cliccando su un elemento della lista, il pannello di destra si popola automaticamente.
    * 🔘 **Pulsante `❌ Elimina Robot`:** Elimina definitivamente la strategia robot selezionata.
* **Pannello di Destra (Configurazione):** * Campi disponibili: `Nome Robot`, un menu a tendina dinamico (`Collega a Account`) che legge direttamente dai bookmaker configurati nella Tab 2, `Trigger Words` (parole chiave separate da virgola), e `Stake Fisso (€)`.
    * *Autosalvataggio in tempo reale:* Il codice usa i "Segnali" di PyQt. Ogni singola lettera che digiti innesca la funzione `save_current_robot_data()` che salva istantaneamente la configurazione nel file `config/robots.yaml`. Non c'è pulsante "Salva", previeni la perdita dati in caso di crash di sistema.
    * 🔘 **Pulsante `➕ Crea Nuovo Robot`:** Il sistema genera un ID univoco in automatico, crea una scheda base chiamata "Nuovo Robot" in fondo alla lista e te la seleziona per permetterti di configurarlo.

#### 5. ☁️ Cloud & API
Il ponte tra il tuo bot locale e il mondo esterno (Telegram e Intelligenza Artificiale).
* **Campi Telegram Cloud & AI:** Permette l'inserimento di `API ID`, `API Hash`, `🔑 Session String` di Telegram (crittografato) e la `🔑 API Key` di OpenRouter (mascherata). Quando apri l'app, il sistema decripta i file dal vault e maschera le chiavi a schermo.
* 🔘 **Pulsante `💾 Salva Chiavi API & Cloud`:** Esegue uno smistamento intelligente:
    1. L'`API ID` e l'`API Hash` vengono salvati in chiaro nel file `config/config.yaml`.
    2. La `Session String` di Telegram viene criptata e salvata nel vault (`telegram_session.dat`).
    3. La `API Key` di OpenRouter viene criptata e salvata nel vault (`openrouter_key.dat`).

#### 6. 📝 Logs
Il monitor della scatola nera.
* **Telemetria in Tempo Reale:** Un'area di testo con sfondo scuro e testo verde ("hacker mode").
* **Dietro le quinte:** Per evitare che la GUI si congeli, il motore principale usa un segnale PyQt asincrono (`self.controller.log_message.connect(self.append_log)`). Qualsiasi evento o azione del bot viene stampato dinamicamente con auto-scroll fluido verso il basso.

---

🌟 Il Ciclo di Vita del Sistema (24/7 Unattended)
Il sistema è progettato per non fermarsi letteralmente mai. Ecco come si comporta in produzione:

Il Risveglio (Supervisor): L'esecuzione non parte da main.py, ma da supervisor.py (installato come Task di Sistema in Windows). Questo guardiano esterno lancia il Core e resta in ascolto.
Il Battito Cardiaco (Heartbeat): Il Core emette un "pulsare" ogni 10 secondi (heartbeat.dat). Se Chromium va in deadlock, la rete salta o il GIL di Python si congela, l'impulso si ferma. Dopo 60 secondi di silenzio, il Supervisor esegue un Hard Kill dell'albero dei processi e resuscita il sistema istantaneamente.
Il Vault (Persistenza Sicura): All'avvio, il sistema non usa file di configurazione nel repository. Accede alla cartella segreta ~/.superagent_data/, decripta le credenziali in memoria tramite AES-256 e carica la sessione immortale di Telegram.
L'Ascolto (Event Bus): Il nodo Telegram legge i segnali dai tipster in modo asincrono e li spara nell'Event Bus.
L'Intelligenza (AI & Rules): L'AI interpreta il segnale, capisce se rispetta le regole dei Robot impostati (stake, esclusione parole, mercato) ed estrapola l'azione.
L'Azione (RPA Stealth V4): Playwright si avvia iniettando il codice Anti-Detect prima del caricamento pagina. Usa curve di Bézier per simulare il movimento del mouse umano, logga, piazza la scommessa, verifica il saldo reale e chiude.
Il Sonno Sicuro (Auto-Backup): Ogni 30 minuti, un demone silenzioso applica un Lock Atomico al database SQLite, clona l'intero Vault crittografato e crea uno .zip (Disaster Recovery).

🚀 Architettura e Moduli Principali

🔐 1. OpSec & Sicurezza Militare (Crypto Vault)
Zero Leak Repository: Nessuna API Key (OpenRouter), password o StringSession viene mai salvata nel codice o in config.yaml.
Storage Isolato: I dati risiedono fuori dal repo, nella root utente (~/.superagent_data/). Disinstallare o aggiornare il bot tramite git non causa perdita di bankroll o impostazioni.
Crittografia AES-256: Le password dei bookmaker inserite nella UI vengono crittografate su disco con una .master.key unica per macchina.
SecretFilter Globale: Il sistema di logging analizza ogni stringa in nanosecondi. Se individua una chiave API o un Token che per errore sta per finire nei log di testo o a schermo, lo maschera irreversibilmente con ██SECRET_MASKED██.

🛟 2. Resilienza e Disaster Recovery
Atomic SQLite Backup: Usa l'API nativa sqlite3.backup() per clonare il database dei fondi a livello C++, prevenendo la corruzione in caso di crash durante la scrittura.
Hard Recycle Preventivo: Se Chromium inizia a soffrire di memory leak superando i 1.2GB di RAM, il processo viene piallato e ricaricato pulito tra una bet e l'altra.
Auto-Boot Windows Task: Script di installazione (setup_vps_task.py) che infila il bot nello SchTasks di Windows con privilegi di amministratore. Se il VPS si riavvia di notte, SuperAgent è già operativo prima del login.

🕵️‍♂️ 3. Ingegneria Anti-Detect
Iniezione JS V4: Modifica di navigator.webdriver, falsificazione dei plugin di sistema, WebGL vendor masking e noise injection su Canvas.
Human Mouse: Il mouse non si teletrasporta (click()), ma viaggia sullo schermo rallentando in prossimità del target con lievi tremolii (Jitter).
Doppia Conferma Finanziaria: Nessuna scommessa viene considerata "Piazzata" se il saldo del bookmaker, letto dal DOM dopo l'azione, non risulta effettivamente decurtato (Circuit Breaker Finanziario).

🧠 4. Piattaforma Multi-Tenant (GUI)
Bookmaker Manager: Gestione di infiniti account (es. Bet365_Main, Sisal_P1) associabili a robot diversi.
Robot & Strategy Manager: Creazione di agenti autonomi indipendenti. Ogni robot ha i propri trigger, la sua gestione del capitale (Fisso o Progressioni) e il suo target di bookmaker.
Selettori AI: Possibilità di iniettare XPath/CSS personalizzati senza toccare il codice, salvandoli stabilmente nel Vault. Utile se il bookmaker cambia interfaccia.
Telegram Session Immortale: Zero file .session temporanei. Accesso tramite StringSession auto-rigenerante che non richiede mai più di un SMS di accesso nella vita.

📁 Struttura del Vault di Produzione
In ambiente Live, il sistema dipende dalla cartella locale e protetta:

C:\Users\TUO_NOME\.superagent_data\
 ├── .master.key               # Chiave militare generata al primo avvio
 ├── heartbeat.dat             # Pulsazione vitale letta dal Supervisor
 ├── money_db.sqlite           # Database tracking scommesse e ROI
 ├── telegram_session.dat      # Login immortale
 ├── openrouter_key.dat        # API Key AI (Mai su GitHub)
 ├── bookmakers.json           # Account bookmaker con PWD crittografate
 ├── robots.json               # I bot e le logiche di puntata
 ├── selectors.json            # Mappatura DOM (XPath/CSS)
 └── backups/
      └── superagent_backup_20260220_1530.zip # Archivio zippato auto-generato

💻 Installazione e Deploy (VPS)
1. Requisiti e Dipendenze
Installa Python 3.10+ e le dipendenze di crittografia e OS:

pip install -r requirements.txt
python -m playwright install chromium

2. Configurazione VPS (Esegui 1 volta sola)
Per rendere il bot immortale ai riavvii di Windows Server, apri il terminale come Amministratore ed esegui:

python setup_vps_task.py

3. Avvio Quotidiano
In produzione, non interagire mai direttamente con il file del codice. Usa il Supervisor:

python supervisor.py

⚠️ Sicurezza e Responsabilità
SuperAgent OS gestisce capitali reali ed è progettato con strumenti elusivi avanzati. Anche se le protezioni interne prevengono il leak di credenziali via log, è responsabilità dell'utente mantenere inviolato il server VPS e il contenuto crittografato della directory ~/.superagent_data/.

```
