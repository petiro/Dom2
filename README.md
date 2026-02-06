# 🚀 SuperAgent - Intelligent RPA Desktop

## 🎯 COSA È

**SuperAgent** combina il meglio di due mondi:

✅ **DomNativeAgent-AI** - Sistema RPA intelligente con auto-apprendimento  
✅ **SuperAgenteAI** - Interfaccia desktop moderna  

**Risultato**: Un agente RPA completo con UI desktop professionale!

## ✨ FEATURES COMPLETE

### 🖥️ Desktop UI (da SuperAgenteAI)
- **Modern PySide6 Interface** - Interfaccia grafica professionale
- **Multi-Tab Layout** - Chat, RPA Monitor, Stats, Settings
- **Dark Theme** - UI moderna e confortevole
- **Real-time Updates** - Monitoring in tempo reale
- **Non-blocking UI** - Threading per operazioni lunghe

### 🧠 AI Learning (da DomNativeAgent-AI)
- **Vision AI** - Comprende immagini e screenshot
- **Telegram Auto-Learning** - Impara nuovi formati messaggi
- **RPA Self-Healing** - Auto-ripara selettori CSS
- **Pattern Recognition** - Riconosce pattern automaticamente
- **Adaptive Behavior** - Si adatta ai cambiamenti

### 🔧 RPA Automation
- **Browser Automation** - Playwright integration
- **Self-Healing Selectors** - Mai più selettori rotti
- **Market Monitoring** - Real-time tracking
- **Auto-Betting** (opzionale) - Scommesse automatiche

## 🚀 QUICK START

### 1. Installazione

```bash
# Estrai il progetto
cd SuperAgent-MERGED

# Installa dipendenze
pip install -r requirements.txt

# Installa browser Playwright (per RPA)
playwright install chromium
```

### 2. Configurazione

Ottieni API key GRATUITA:
1. Vai su: **https://openrouter.ai/keys**
2. Registrati (gratis)
3. Crea API key
4. Apri `config/config.yaml` e aggiungi la key:

```yaml
openrouter:
  api_key: "sk-or-v1-YOUR_KEY_HERE"  # ← Incolla qui
```

### 3. Avvia

```bash
python main.py
```

**FATTO!** 🎉

L'app desktop si aprirà con tutte le funzionalità disponibili.

## 📊 INTERFACCIA

### Tab 1: 💬 AI Chat
- Input area per messaggi
- Chat history
- AI responses in tempo reale
- Non-blocking UI (threading)

### Tab 2: 🔧 RPA Monitor
- Status agent in tempo reale
- Uptime tracker
- Selector healing history
- Start/Stop controls
- Test healing button

### Tab 3: 📊 Statistics
- Telegram learning stats
- RPA healing stats
- Success rates
- Pattern count
- Auto-update ogni secondo

### Tab 4: ⚙️ Settings
- API key configuration
- Model selection
- RPA settings (autobet, headless)
- Learning settings
- Save/Load config

## 🎮 COME USARE

### Chat con AI

1. Vai al tab **"AI Chat"**
2. Scrivi il tuo messaggio
3. Clicca **"Send"**
4. Aspetta risposta (non blocca UI!)

### Monitorare RPA

1. Vai al tab **"RPA Monitor"**
2. Clicca **"Start Agent"**
3. Monitora status e healing in tempo reale
4. Vedi selector healing nella tabella

### Vedere Statistiche

1. Vai al tab **"Statistics"**
2. Clicca **"Refresh Stats"**
3. Vedi:
   - Telegram messages parsed
   - Patterns learned
   - Success rate
   - RPA healings
   - Auto-updates

### Configurare

1. Vai al tab **"Settings"**
2. Modifica impostazioni:
   - API key
   - Model
   - RPA settings
   - Learning settings
3. Clicca **"Save Settings"**

## 🏗️ ARCHITETTURA

```
SuperAgent-MERGED/
├── main.py                     # Entry point
│
├── ui/                         # Desktop UI
│   └── desktop_app.py          # PySide6 interface
│
├── ai/                         # AI Components (da DomNativeAgent)
│   ├── vision_learner.py       # Core AI
│   ├── telegram_learner.py     # Telegram auto-learning
│   └── rpa_healer.py           # Self-healing RPA
│
├── core/                       # Core utilities
│   ├── utils.py                # Helper functions
│   └── dom_executor_playwright.py  # Browser automation
│
├── config/
│   └── config.yaml             # Configuration
│
├── data/                       # Learning data (auto-created)
│   ├── telegram_patterns.json
│   ├── healing_history.json
│   └── superagent.db
│
└── logs/                       # Logs (auto-created)
    └── superagent.log
```

## 🔧 CONFIGURAZIONE AVANZATA

### API Settings

```yaml
openrouter:
  api_key: "your_key"
  model: "google/gemini-2.0-flash-exp:free"
```

**Modelli free disponibili:**
- `google/gemini-2.0-flash-exp:free`
- `meta-llama/llama-3.2-3b-instruct:free`
- `google/gemini-flash-1.5:free`

### RPA Settings

```yaml
rpa:
  enabled: false  # true per abilitare
  headless: true  # false per vedere browser
  autobet: false  # ⚠️ PERICOLOSO! Solo per esperti
  pin: "0503"  # PIN login rapido
```

### Learning Settings

```yaml
learning:
  telegram:
    enabled: true
    min_examples: 3  # Pattern dopo N esempi
    
  rpa_healing:
    enabled: true
    auto_update: true  # Auto-update selectors.yaml
```

## 🎨 TEMI

### Dark Theme (default)
```yaml
ui:
  theme: "dark"
```

### Light Theme
```yaml
ui:
  theme: "light"
```

## 💾 DATI SALVATI

### Telegram Patterns
`data/telegram_patterns.json`
```json
{
  "patterns": [...],
  "statistics": {
    "total_messages": 150,
    "learned_patterns": 3,
    "success_rate": 0.98
  }
}
```

### Healing History
`data/healing_history.json`
```json
[
  {
    "timestamp": "2025-02-06T10:30:00",
    "selector_key": "bet_button",
    "old_selector": "button.old",
    "new_selector": "button.new",
    "auto_updated": true
  }
]
```

### Database
`data/superagent.db` (SQLite)
- Conversazioni salvate
- Memoria AI
- Cache

## 📊 LOGGING

### Console
Output in tempo reale:
```
2025-02-06 10:30:45 - SuperAgent - INFO - ✅ AI initialized
2025-02-06 10:30:46 - SuperAgent - INFO - 🖥️ Starting desktop application...
```

### File
`logs/superagent.log` - Log completo con rotazione

## 🐛 TROUBLESHOOTING

### ❌ "No API key found"
**Fix**: Aggiungi API key in `config/config.yaml` o nel tab Settings

### ❌ "Playwright not found"
**Fix**: `playwright install chromium`

### ❌ "PySide6 import error"
**Fix**: `pip install PySide6>=6.6.0`

### ⚠️ UI si blocca
**Fix**: Già risolto! Usa threading per operazioni lunghe

### ⚠️ Dark theme non funziona
**Fix**: Riavvia app dopo cambio tema

## 🎯 ROADMAP

### ✅ Versione 1.0 (COMPLETA)
- [x] Desktop UI moderna
- [x] AI Chat integration
- [x] RPA monitoring
- [x] Statistics dashboard
- [x] Settings panel
- [x] Dark theme
- [x] Threading non-blocking

### 🚧 Versione 1.1 (Prossima)
- [ ] Telegram integration UI
- [ ] Browser preview in UI
- [ ] Advanced charting
- [ ] Export statistics
- [ ] Multiple profiles
- [ ] Plugin system

### 🔮 Versione 2.0 (Futuro)
- [ ] Cloud sync
- [ ] Multi-user
- [ ] Mobile app companion
- [ ] Advanced AI models
- [ ] Voice commands

## 📚 DOCUMENTAZIONE

### Guide
1. **README.md** (questo file) - Overview e quick start
2. **AI_LEARNING_GUIDE.md** - Guida AI dettagliata
3. **UI_GUIDE.md** - Guida interfaccia

### Esempi
- `examples/chat_example.py` - Esempio chat AI
- `examples/rpa_example.py` - Esempio RPA
- `examples/learning_example.py` - Esempio auto-learning

## 🤝 CONTRIBUIRE

### Struttura branch
- `main` - Stabile
- `develop` - Sviluppo
- `feature/*` - Nuove feature

### Test
```bash
pytest tests/
```

### Code style
```bash
black .
pylint superagent/
```

## 📜 LICENSE

MIT License - Vedi LICENSE file

## 🙏 CREDITS

- **DomNativeAgent-AI** - Sistema RPA intelligente
- **SuperAgenteAI** - UI desktop
- **OpenRouter** - API gratuita
- **PySide6** - Qt for Python
- **Playwright** - Browser automation

---

## 🚀 START NOW!

```bash
# 1. Install
pip install -r requirements.txt
playwright install chromium

# 2. Configure
# Add API key in config/config.yaml

# 3. Run
python main.py

# 4. Enjoy! 🎉
```

---

**Made with ❤️ combining the best of AI and Desktop UI**

*Zero-maintenance, self-learning, beautiful interface*
