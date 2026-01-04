"""
Candidate Index - אינדקס מהיר למועמדים לפתרון תשבץ

מאפשר:
1. חיפוש מהיר של מועמדים לפי אורך ותבנית
2. סינון מועמדים לא תואמים אחרי גילוי אותיות
3. מעקב אחר מקור ורמת ביטחון
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Iterator
from collections import defaultdict
import re


@dataclass
class CandidateWord:
    """מועמד לתשובה בתשבץ"""

    word: str                      # המילה עצמה ("במבה")
    clue_id: str                   # מאיזה clue הגיעה
    confidence: float              # ביטחון בתשובה הזו (0.0-1.0)
    clue_certainty: float          # ודאות ההגדרה (0.0-1.0)
    query_phase: int = 1           # באיזה שלב התקבלה (1, 2, 3...)
    known_letters_snapshot: str = ""  # תבנית בזמן השאילתא ("____" או "_ב__")

    @property
    def length(self) -> int:
        return len(self.word)

    @property
    def combined_score(self) -> float:
        """ציון משולב - ביטחון * ודאות"""
        return self.confidence * self.clue_certainty

    def matches_pattern(self, pattern: str) -> bool:
        """
        בודק אם המילה מתאימה לתבנית.
        תבנית: "_ב_מ_" כאשר _ = אות לא ידועה
        """
        if len(self.word) != len(pattern):
            return False

        for i, char in enumerate(pattern):
            if char != '_' and char != self.word[i]:
                return False

        return True

    def get_letter_at(self, position: int) -> Optional[str]:
        """מחזיר אות במיקום מסוים"""
        if 0 <= position < len(self.word):
            return self.word[position]
        return None


class CandidateIndex:
    """
    אינדקס מרכזי לכל המועמדים.

    מאפשר:
    - חיפוש לפי clue_id
    - חיפוש לפי אורך
    - סינון לפי תבנית אותיות
    - סינון מועמדים לא תואמים
    """

    def __init__(self):
        # מיפוי ראשי: clue_id → רשימת מועמדים
        self._by_clue: Dict[str, List[CandidateWord]] = defaultdict(list)

        # מיפוי לפי אורך: length → set of words
        self._by_length: Dict[int, Set[str]] = defaultdict(set)

        # אינדקס לפי (אורך, מיקום, אות) → set of words
        # מאפשר שאילתות כמו "כל המילים באורך 5 עם 'ב' במיקום 1"
        self._position_index: Dict[Tuple[int, int, str], Set[str]] = defaultdict(set)

        # מעקב אחר מילים שנכשלו (לא לנסות שוב)
        self._failed: Dict[str, Set[str]] = defaultdict(set)  # clue_id → {failed words}

        # סטטיסטיקות
        self._total_added = 0
        self._total_filtered = 0

    def add_candidate(self, candidate: CandidateWord) -> None:
        """הוספת מועמד לאינדקס"""
        # בדיקה אם כבר נכשל
        if candidate.word in self._failed.get(candidate.clue_id, set()):
            return

        # בדיקה אם כבר קיים - עדכון confidence אם צריך
        existing = self._find_existing(candidate.clue_id, candidate.word)
        if existing:
            # עדכון ממוצע משוקלל של confidence
            existing.confidence = (existing.confidence + candidate.confidence) / 2
            existing.query_phase = max(existing.query_phase, candidate.query_phase)
            return

        # הוספה לאינדקסים
        self._by_clue[candidate.clue_id].append(candidate)
        self._by_length[candidate.length].add(candidate.word)

        # אינדקס לפי מיקום ואות
        for i, letter in enumerate(candidate.word):
            self._position_index[(candidate.length, i, letter)].add(candidate.word)

        self._total_added += 1

    def add_candidates(self, candidates: List[CandidateWord]) -> None:
        """הוספת מספר מועמדים"""
        for c in candidates:
            self.add_candidate(c)

    def _find_existing(self, clue_id: str, word: str) -> Optional[CandidateWord]:
        """מחפש מועמד קיים"""
        for c in self._by_clue.get(clue_id, []):
            if c.word == word:
                return c
        return None

    def get_candidates_for_clue(
        self,
        clue_id: str,
        pattern: Optional[str] = None,
        exclude_failed: bool = True
    ) -> List[CandidateWord]:
        """
        מחזיר מועמדים להגדרה מסוימת.

        Args:
            clue_id: מזהה ההגדרה
            pattern: תבנית לסינון (אופציונלי)
            exclude_failed: האם להחריג מילים שנכשלו

        Returns:
            רשימת מועמדים ממוינת לפי ביטחון (גבוה לנמוך)
        """
        candidates = self._by_clue.get(clue_id, [])

        # סינון לפי תבנית
        if pattern:
            candidates = [c for c in candidates if c.matches_pattern(pattern)]

        # סינון מילים שנכשלו
        if exclude_failed:
            failed = self._failed.get(clue_id, set())
            candidates = [c for c in candidates if c.word not in failed]

        # מיון לפי ביטחון
        return sorted(candidates, key=lambda c: c.confidence, reverse=True)

    def get_valid_candidates_for_clue(
        self,
        clue_id: str,
        pattern: str
    ) -> List[CandidateWord]:
        """
        מחזיר רק מועמדים תקינים (מתאימים לתבנית ולא נכשלו).
        קיצור ל-get_candidates_for_clue עם pattern ו-exclude_failed=True.
        """
        return self.get_candidates_for_clue(clue_id, pattern=pattern, exclude_failed=True)

    def get_best_candidate(
        self,
        clue_id: str,
        pattern: str
    ) -> Optional[CandidateWord]:
        """מחזיר את המועמד הטוב ביותר (אם יש)"""
        candidates = self.get_valid_candidates_for_clue(clue_id, pattern)
        return candidates[0] if candidates else None

    def has_single_valid_candidate(self, clue_id: str, pattern: str) -> bool:
        """בודק אם יש מועמד תקין יחיד"""
        candidates = self.get_valid_candidates_for_clue(clue_id, pattern)
        return len(candidates) == 1

    def get_candidate_count(self, clue_id: str, pattern: Optional[str] = None) -> int:
        """מחזיר מספר מועמדים תקינים"""
        return len(self.get_candidates_for_clue(clue_id, pattern=pattern))

    def filter_by_letter(
        self,
        clue_id: str,
        position: int,
        letter: str,
        word_length: int
    ) -> int:
        """
        מסנן מועמדים שלא מתאימים לאות במיקום מסוים.

        Args:
            clue_id: מזהה ההגדרה
            position: מיקום האות (0-indexed)
            letter: האות הנדרשת
            word_length: אורך המילה

        Returns:
            מספר מועמדים שהוסרו
        """
        candidates = self._by_clue.get(clue_id, [])
        initial_count = len(candidates)

        # סינון מועמדים לא מתאימים
        valid = [
            c for c in candidates
            if c.length == word_length and c.get_letter_at(position) == letter
        ]

        self._by_clue[clue_id] = valid
        filtered = initial_count - len(valid)
        self._total_filtered += filtered

        return filtered

    def filter_by_pattern(self, clue_id: str, pattern: str) -> int:
        """
        מסנן מועמדים שלא מתאימים לתבנית.

        Args:
            clue_id: מזהה ההגדרה
            pattern: תבנית ("_ב_מ_")

        Returns:
            מספר מועמדים שהוסרו
        """
        candidates = self._by_clue.get(clue_id, [])
        initial_count = len(candidates)

        valid = [c for c in candidates if c.matches_pattern(pattern)]

        self._by_clue[clue_id] = valid
        filtered = initial_count - len(valid)
        self._total_filtered += filtered

        return filtered

    def mark_as_failed(self, clue_id: str, word: str) -> None:
        """מסמן מילה כנכשלה (לא לנסות שוב)"""
        self._failed[clue_id].add(word)

        # הסרה מרשימת המועמדים
        self._by_clue[clue_id] = [
            c for c in self._by_clue.get(clue_id, [])
            if c.word != word
        ]

    def remove_candidate(self, clue_id: str, word: str) -> bool:
        """
        מסיר מועמד ספציפי (בלי לסמן כנכשל).

        Returns:
            True אם הוסר, False אם לא נמצא
        """
        candidates = self._by_clue.get(clue_id, [])
        initial_count = len(candidates)

        self._by_clue[clue_id] = [c for c in candidates if c.word != word]

        return len(self._by_clue[clue_id]) < initial_count

    def clear_clue(self, clue_id: str) -> None:
        """מנקה את כל המועמדים להגדרה"""
        self._by_clue[clue_id] = []

    def get_all_clue_ids(self) -> List[str]:
        """מחזיר את כל ה-clue_ids באינדקס"""
        return list(self._by_clue.keys())

    def get_clues_with_single_candidate(self, patterns: Dict[str, str]) -> List[str]:
        """
        מחזיר clue_ids שיש להם מועמד תקין יחיד.

        Args:
            patterns: מיפוי clue_id → pattern

        Returns:
            רשימת clue_ids
        """
        result = []
        for clue_id, pattern in patterns.items():
            if self.has_single_valid_candidate(clue_id, pattern):
                result.append(clue_id)
        return result

    def get_clues_sorted_by_confidence(
        self,
        patterns: Dict[str, str],
        unsolved_only: List[str] = None
    ) -> List[Tuple[str, CandidateWord]]:
        """
        מחזיר הגדרות ממוינות לפי ביטחון המועמד הטוב ביותר.

        Args:
            patterns: מיפוי clue_id → pattern
            unsolved_only: רשימת clue_ids שלא נפתרו (אופציונלי)

        Returns:
            רשימת (clue_id, best_candidate) ממוינת
        """
        result = []

        clue_ids = unsolved_only if unsolved_only else list(patterns.keys())

        for clue_id in clue_ids:
            pattern = patterns.get(clue_id, '')
            best = self.get_best_candidate(clue_id, pattern)
            if best:
                result.append((clue_id, best))

        # מיון לפי combined_score (confidence * certainty)
        return sorted(result, key=lambda x: x[1].combined_score, reverse=True)

    def merge_new_candidates(
        self,
        new_candidates: List[CandidateWord],
        current_phase: int
    ) -> int:
        """
        מזג מועמדים חדשים מ-re-query.

        Args:
            new_candidates: מועמדים חדשים
            current_phase: מספר השלב הנוכחי

        Returns:
            מספר מועמדים שנוספו/עודכנו
        """
        updated = 0
        for c in new_candidates:
            c.query_phase = current_phase
            existing = self._find_existing(c.clue_id, c.word)

            if existing:
                # עדכון - נותן משקל יתר לתוצאה החדשה (עם יותר אותיות ידועות)
                existing.confidence = (existing.confidence + c.confidence * 2) / 3
                existing.query_phase = current_phase
            else:
                self.add_candidate(c)

            updated += 1

        return updated

    def get_statistics(self) -> Dict:
        """מחזיר סטטיסטיקות על האינדקס"""
        total_candidates = sum(len(v) for v in self._by_clue.values())
        clues_with_candidates = sum(1 for v in self._by_clue.values() if v)
        failed_words = sum(len(v) for v in self._failed.values())

        avg_candidates = total_candidates / clues_with_candidates if clues_with_candidates > 0 else 0

        return {
            'total_clues': len(self._by_clue),
            'clues_with_candidates': clues_with_candidates,
            'total_candidates': total_candidates,
            'avg_candidates_per_clue': round(avg_candidates, 2),
            'total_added': self._total_added,
            'total_filtered': self._total_filtered,
            'failed_words': failed_words,
            'unique_words': len(self._by_length.get(max(self._by_length.keys(), default=0), set()))
        }

    def clear(self) -> None:
        """מנקה את כל האינדקס"""
        self._by_clue.clear()
        self._by_length.clear()
        self._position_index.clear()
        self._failed.clear()
        self._total_added = 0
        self._total_filtered = 0


def pattern_to_regex(pattern: str) -> re.Pattern:
    """ממיר תבנית תשבץ לregex"""
    regex_str = ""
    for char in pattern:
        if char == '_':
            regex_str += '.'  # כל תו
        else:
            regex_str += re.escape(char)
    return re.compile(f"^{regex_str}$")
