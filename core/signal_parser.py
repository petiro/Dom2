import re


class TelegramSignalParser:
    def parse(self, text):
        """Estrae team e calcola l'Over Successivo basandosi sulla somma gol."""
        if not text:
            return {}

        # 1. Estrazione Team (dopo emoji VS o varianti)
        teams_match = re.search(r"(?:🆚|VS|vs|⚽)\s*(.*?)\n", text)
        match_name = teams_match.group(1).strip() if teams_match else None

        # 2. Estrazione Punteggio per calcolo Over
        score_match = re.search(r"(\d+)\s*-\s*(\d+)", text)
        if score_match:
            h_goals = int(score_match.group(1))
            a_goals = int(score_match.group(2))
            target_over = (h_goals + a_goals) + 0.5
            score_str = f"{h_goals}-{a_goals}"
        else:
            target_over = 0.5
            score_str = "0-0"

        # FIX BUG-01: Usa chiave 'teams' invece di 'match'
        return {
            "teams": match_name,
            "market": f"Over {target_over}",
            "raw_text": text,
            "score": score_str
        }
