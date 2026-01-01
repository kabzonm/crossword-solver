"""
Clue Solver Service
קבלת תשובות אפשריות להגדרות מ-LLM
"""

import json
import time
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

from models.clue_entry import ClueEntry

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class SolverResult:
    """תוצאת פתרון הגדרה"""
    candidates: List[Tuple[str, float]]  # [(תשובה, ביטחון), ...]
    processing_time: float = 0.0
    error: Optional[str] = None


class ClueSolver:
    """
    מקבל תשובות אפשריות להגדרות תשבץ מ-Claude.

    מקבל:
    - טקסט ההגדרה
    - אורך התשובה
    - אותיות ידועות (מהצלבות)

    מחזיר:
    - רשימה של 10 תשובות אפשריות עם ציוני ביטחון
    """

    SOLVE_PROMPT = """You are a Hebrew crossword puzzle expert. Solve this clue.

Clue: "{clue_text}"
Answer length: {length} letters
{constraints_info}

IMPORTANT:
- This is a HEBREW crossword - answers must be in Hebrew
- The answer must be EXACTLY {length} Hebrew letters
- Consider wordplay, puns, and double meanings common in Hebrew crosswords
{known_letters_hint}

Provide your top 10 answer candidates, ranked by likelihood.

Respond with JSON only:
{{
  "candidates": [
    {{"answer": "תשובה", "confidence": 0.95, "explanation": "brief reason"}},
    {{"answer": "אחרת", "confidence": 0.80, "explanation": "brief reason"}},
    ...
  ]
}}

Rules:
1. Each answer must be EXACTLY {length} Hebrew letters (no spaces, no punctuation)
2. Confidence is 0.0 to 1.0
3. If you're unsure, still provide your best guesses with lower confidence
4. Consider common Hebrew crossword patterns and conventions
"""

    BATCH_SOLVE_PROMPT = """You are a Hebrew crossword puzzle expert. Solve these clues.

{clues_list}

IMPORTANT:
- This is a HEBREW crossword - all answers must be in Hebrew
- Each answer must match EXACTLY the specified length
- Consider wordplay, puns, and double meanings

Respond with JSON only:
{{
  "solutions": [
    {{
      "clue_id": "clue_0_0_full",
      "candidates": [
        {{"answer": "תשובה", "confidence": 0.95}},
        {{"answer": "אחרת", "confidence": 0.80}}
      ]
    }},
    ...
  ]
}}
"""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        """
        Args:
            api_key: Claude API key
            model: מודל Claude לשימוש
        """
        self.api_key = api_key
        self.model = model
        self.client = None
        self._cache: Dict[str, SolverResult] = {}  # cache לתשובות

        if ANTHROPIC_AVAILABLE and api_key:
            self.client = anthropic.Anthropic(api_key=api_key)

    def solve_clue(self, clue: ClueEntry, use_cache: bool = True) -> SolverResult:
        """
        פותר הגדרה בודדת.

        Args:
            clue: ההגדרה לפתרון
            use_cache: האם להשתמש ב-cache

        Returns:
            SolverResult עם רשימת תשובות אפשריות
        """
        if not self.client:
            return SolverResult(
                candidates=[],
                error="Claude client not available"
            )

        if clue.answer_length == 0:
            return SolverResult(
                candidates=[],
                error="Answer length is 0"
            )

        # בדיקת cache
        cache_key = self._get_cache_key(clue)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        start_time = time.time()

        try:
            # בניית הפרומפט
            constraints_info = ""
            known_letters_hint = ""

            if clue.known_letters:
                constraint_str = clue.get_constraint_string()
                constraints_info = f"Known letters pattern: {constraint_str}"
                known_letters_hint = f"- The answer must match this pattern: {constraint_str} (where _ is unknown)"

            prompt = self.SOLVE_PROMPT.format(
                clue_text=clue.text,
                length=clue.answer_length,
                constraints_info=constraints_info,
                known_letters_hint=known_letters_hint
            )

            # קריאה לקלוד
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # פענוח התשובה
            result = self._parse_response(response.content[0].text, clue)
            result.processing_time = time.time() - start_time

            # שמירה ב-cache
            if use_cache:
                self._cache[cache_key] = result

            return result

        except Exception as e:
            return SolverResult(
                candidates=[],
                processing_time=time.time() - start_time,
                error=str(e)
            )

    def solve_batch(
        self,
        clues: List[ClueEntry],
        max_per_request: int = 10
    ) -> Dict[str, SolverResult]:
        """
        פותר מספר הגדרות בבת אחת (יעיל יותר).

        Args:
            clues: רשימת הגדרות
            max_per_request: מקסימום הגדרות בקריאה אחת

        Returns:
            מיפוי clue_id → SolverResult
        """
        results = {}

        if not self.client:
            for clue in clues:
                results[clue.id] = SolverResult(
                    candidates=[],
                    error="Claude client not available"
                )
            return results

        # חלוקה לקבוצות
        for i in range(0, len(clues), max_per_request):
            batch = clues[i:i + max_per_request]
            batch_results = self._solve_batch_internal(batch)
            results.update(batch_results)

        return results

    def _solve_batch_internal(self, clues: List[ClueEntry]) -> Dict[str, SolverResult]:
        """פותר קבוצה של הגדרות"""
        results = {}
        start_time = time.time()

        try:
            # בניית רשימת ההגדרות
            clues_list = []
            for clue in clues:
                constraint_str = clue.get_constraint_string()
                clue_info = f"- ID: {clue.id}\n  Clue: \"{clue.text}\"\n  Length: {clue.answer_length}"
                if constraint_str and '_' in constraint_str:
                    clue_info += f"\n  Pattern: {constraint_str}"
                clues_list.append(clue_info)

            prompt = self.BATCH_SOLVE_PROMPT.format(
                clues_list="\n".join(clues_list)
            )

            # קריאה לקלוד
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # פענוח
            processing_time = time.time() - start_time
            results = self._parse_batch_response(response.content[0].text, clues)

            # עדכון זמן עיבוד
            for result in results.values():
                result.processing_time = processing_time / len(clues)

        except Exception as e:
            for clue in clues:
                results[clue.id] = SolverResult(
                    candidates=[],
                    processing_time=time.time() - start_time,
                    error=str(e)
                )

        return results

    def _parse_response(self, response_text: str, clue: ClueEntry) -> SolverResult:
        """פענוח תשובה בודדת"""
        try:
            # חילוץ JSON
            json_str = response_text
            if '{' in json_str:
                start = json_str.find('{')
                end = json_str.rfind('}') + 1
                json_str = json_str[start:end]

            data = json.loads(json_str)

            candidates = []
            for cand in data.get('candidates', []):
                answer = cand.get('answer', '')

                # סינון תשובות לא תקינות
                if len(answer) != clue.answer_length:
                    continue

                # בדיקת התאמה לאותיות ידועות
                if not clue.matches_answer(answer):
                    continue

                confidence = cand.get('confidence', 0.5)
                candidates.append((answer, confidence))

            # מיון לפי ביטחון
            candidates.sort(key=lambda x: x[1], reverse=True)

            return SolverResult(candidates=candidates[:10])

        except json.JSONDecodeError as e:
            return SolverResult(
                candidates=[],
                error=f"JSON parse error: {e}"
            )

    def _parse_batch_response(
        self,
        response_text: str,
        clues: List[ClueEntry]
    ) -> Dict[str, SolverResult]:
        """פענוח תשובה לקבוצה"""
        results = {}
        clue_map = {c.id: c for c in clues}

        try:
            json_str = response_text
            if '{' in json_str:
                start = json_str.find('{')
                end = json_str.rfind('}') + 1
                json_str = json_str[start:end]

            data = json.loads(json_str)

            for solution in data.get('solutions', []):
                clue_id = solution.get('clue_id', '')
                clue = clue_map.get(clue_id)

                if not clue:
                    continue

                candidates = []
                for cand in solution.get('candidates', []):
                    answer = cand.get('answer', '')

                    if len(answer) != clue.answer_length:
                        continue

                    if not clue.matches_answer(answer):
                        continue

                    confidence = cand.get('confidence', 0.5)
                    candidates.append((answer, confidence))

                candidates.sort(key=lambda x: x[1], reverse=True)
                results[clue_id] = SolverResult(candidates=candidates[:10])

        except json.JSONDecodeError as e:
            for clue in clues:
                results[clue.id] = SolverResult(
                    candidates=[],
                    error=f"JSON parse error: {e}"
                )

        # וידוא שכל ההגדרות קיבלו תוצאה
        for clue in clues:
            if clue.id not in results:
                results[clue.id] = SolverResult(
                    candidates=[],
                    error="No result in response"
                )

        return results

    def _get_cache_key(self, clue: ClueEntry) -> str:
        """יוצר מפתח cache להגדרה"""
        return f"{clue.text}|{clue.answer_length}|{clue.get_constraint_string()}"

    def clear_cache(self) -> None:
        """ניקוי ה-cache"""
        self._cache.clear()

    def get_cache_stats(self) -> Dict:
        """סטטיסטיקות cache"""
        return {
            'cached_clues': len(self._cache),
            'total_candidates': sum(
                len(r.candidates) for r in self._cache.values()
            )
        }
