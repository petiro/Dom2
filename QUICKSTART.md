# ⚡ QUICKSTART - SuperAgent

## 🎯 Get Running in 3 Minutes

### Step 1: Install (1 min)

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

**Manual:**
```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 2: Configure (1 min)

1. Get FREE API key: **https://openrouter.ai/keys**
2. Open `config/config.yaml`
3. Paste your key:

```yaml
openrouter:
  api_key: "sk-or-v1-YOUR_KEY_HERE"  # ← HERE!
```

### Step 3: Run! (30 sec)

```bash
python main.py
```

**DONE!** The desktop app opens! 🎉

## 🎮 First Use

### Try AI Chat

1. Click tab **"AI Chat"**
2. Type: "Hello! What can you do?"
3. Click **"Send"**
4. Get AI response!

### Check Statistics

1. Click tab **"Statistics"**
2. Click **"Refresh Stats"**
3. See learning progress

### Configure Settings

1. Click tab **"Settings"**
2. Customize options
3. Click **"Save Settings"**

## 🐛 Quick Fixes

**❌ "No API key"**
→ Add key in `config/config.yaml`

**❌ "Playwright not found"**
→ Run: `playwright install chromium`

**❌ "PySide6 error"**
→ Run: `pip install PySide6>=6.6.0`

## 📚 Learn More

- **Full docs:** README.md
- **AI guide:** AI_LEARNING_GUIDE.md
- **Config:** config/config.yaml

## 🆘 Need Help?

1. Check `logs/superagent.log`
2. Read README.md
3. Check configuration

---

**Enjoy SuperAgent!** 🚀
