import re

class TelegramSignalParser:
    def parse(self, text):
        """Estrae team e calcola l'Over Successivo basandosi sulla somma gol."""
        # 1. Estrazione Team (dopo emoji VS)
        teams_match = re.search(r"🆚\s*(.*?)\n", text)
        match_name = teams_match.group(1).strip() if teams_match else None

        # 2. Estrazione Punteggio per calcolo Over
        # Cerca pattern numerico "X - Y"
        score_match = re.search(r"(\d+)\s*-\s*(\d+)", text)
        if score_match:
            h_goals = int(score_match.group(1))
            a_goals = int(score_match.group(2))
            # LOGICA BLIND OVER: Somma attuale + 0.5
            target_over = (h_goals + a_goals) + 0.5
        else:
            # Fallback se punteggio non trovato (es. 0-0 inizio)
            target_over = 0.5

        return {
            "match": match_name,
            "market": f"Over {target_over}",
            "raw_text": text
        }
