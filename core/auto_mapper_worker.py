import time
import re
import yaml
import os
from PySide6.QtCore import QObject, Signal
from core.config_paths import CONFIG_DIR

class AutoMapperWorker(QObject):
    finished = Signal(dict)
    log = Signal(str)

    def __init__(self, executor, url):
        super().__init__()
        self.executor = executor
        self.url = url

    def run(self):
        try:
            self.log.emit(f"🚀 AI Auto-Mapping: {self.url}")

            if not self.executor.launch_browser():
                self.log.emit("❌ Browser non avviato")
                self.finished.emit({})
                return

            page = self.executor.page
            try:
                page.goto(self.url, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
            except:
                self.log.emit("⚠️ Timeout pagina, continuo")

            self._auto_scroll(page)

            # CDP invisibile
            self.log.emit("🔌 Connessione CDP interna...")
            cdp = page.context.new_cdp_session(page)
            cdp.send("DOM.enable")

            self.log.emit("🕷️ Scansione DOM profondo...")
            resp = cdp.send("DOM.getFlattenedDocument", {
                "depth": -1,
                "pierce": True
            })

            nodes = resp.get("nodes", [])
            self.log.emit(f"🔍 Nodi analizzati: {len(nodes)}")

            elements = self._extract(nodes)
            selectors = self._ai_match(elements)
            self._save(selectors)

            self.log.emit(f"✅ MAPPING COMPLETATO: {len(selectors)} campi.")
            self.finished.emit(selectors)

        except Exception as e:
            self.log.emit(f"❌ Mapper crash: {e}")
            self.finished.emit({})

    def _auto_scroll(self, page):
        last = 0
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            h = page.evaluate("document.body.scrollHeight")
            if h == last: break
            last = h

    def _extract(self, nodes):
        found = []
        for n in nodes:
            if self._is_interactive(n):
                css = self._css(n)
                if css:
                    found.append({
                        "tag": n.get("nodeName","").lower(),
                        "css": css,
                        "text": self._text(n),
                        "class": self._attr(n,"class")
                    })
        return found

    def _ai_match(self, elements):
        selectors = {}
        keys = {
            "stake_input": ["stake","importo","puntata","amount","wager"],
            "place_button": ["scommetti","bet","place","gioca","piazza"],
            "login_button": ["login","accedi","entra"],
            "odds_value": ["quota","odd","price"],
            "search_box": ["search","cerca","trova"]
        }

        for el in elements:
            fingerprint = (el["tag"]+" "+el["text"]+" "+el["class"]).lower()
            for field,words in keys.items():
                if field in selectors: continue
                if field=="stake_input" and el["tag"]!="input": continue
                
                if any(w in fingerprint for w in words):
                    selectors[field]=el["css"]
                    self.log.emit(f"✨ Match: {field} -> {el['css']}")

        return selectors

    def _save(self, selectors):
        if not selectors: return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        path = os.path.join(CONFIG_DIR, "selectors_auto.yaml")
        try:
            with open(path, "w") as f:
                yaml.dump(selectors, f, default_flow_style=False)
            self.log.emit(f"💾 Salvato: {path}")
        except: pass

    # Helpers CDP
    def _attrs(self, node):
        a = node.get("attributes", [])
        return dict(zip(a[::2], a[1::2]))

    def _attr(self, node, name):
        return self._attrs(node).get(name, "")

    def _text(self, node):
        a = self._attrs(node)
        return (a.get("aria-label","") + a.get("placeholder","") + a.get("value",""))

    def _is_interactive(self, node):
        tag = node.get("nodeName","").upper()
        if tag in ["BUTTON", "INPUT", "A", "SELECT", "TEXTAREA"]: return True
        attrs = self._attrs(node)
        if attrs.get("role") in ["button", "link", "textbox"]: return True
        cls = attrs.get("class","").lower()
        if any(x in cls for x in ["odd", "price", "quota", "btn"]): return True
        return False

    def _css(self, node):
        attrs = self._attrs(node)
        tag = node.get("nodeName","").lower()
        
        if "id" in attrs and len(attrs["id"]) < 32 and not re.search(r'\d{5,}', attrs["id"]):
            return f"#{attrs['id']}"
            
        for k in attrs:
            if k.startswith("data-"): return f"{tag}[{k}='{attrs[k]}']"
            
        if "name" in attrs: return f"{tag}[name='{attrs['name']}']"
        
        if "aria-label" in attrs:
            clean = attrs['aria-label'].replace("'", "")
            return f"{tag}[aria-label='{clean}']"
            
        if "class" in attrs:
            for cls in attrs["class"].split():
                if not re.search(r"css-|sc-|flex|grid", cls):
                    return f"{tag}.{cls}"
        return None
