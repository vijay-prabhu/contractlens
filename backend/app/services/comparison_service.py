"""Document version comparison service."""
import difflib
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from uuid import UUID
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_version import DocumentVersion
from app.models.clause import Clause
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Type of change between versions."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class ClauseChange:
    """Represents a change to a clause between versions."""
    change_type: ChangeType
    clause_type: str

    # For added/unchanged: new clause info
    new_clause_id: Optional[UUID] = None
    new_text: Optional[str] = None
    new_risk_level: Optional[str] = None
    new_risk_score: Optional[float] = None

    # For removed: old clause info
    old_clause_id: Optional[UUID] = None
    old_text: Optional[str] = None
    old_risk_level: Optional[str] = None
    old_risk_score: Optional[float] = None

    # For modified: both + diff info
    text_diff: Optional[str] = None
    similarity_score: Optional[float] = None
    risk_change: Optional[str] = None  # "increased", "decreased", "unchanged"


@dataclass
class TextDiff:
    """Text-level diff between two versions."""
    additions: int = 0
    deletions: int = 0
    diff_html: str = ""
    diff_lines: List[str] = field(default_factory=list)


@dataclass
class RiskSummary:
    """Summary of risk changes between versions."""
    old_overall_score: float = 0.0
    new_overall_score: float = 0.0
    risk_trend: str = "unchanged"  # "increased", "decreased", "unchanged"
    critical_added: int = 0
    critical_removed: int = 0
    high_risk_added: int = 0
    high_risk_removed: int = 0


@dataclass
class ComparisonResult:
    """Complete comparison result between two document versions."""
    version1_id: UUID
    version2_id: UUID
    version1_number: int
    version2_number: int

    # Text-level comparison
    text_diff: TextDiff

    # Clause-level comparison
    clause_changes: List[ClauseChange]
    clauses_added: int = 0
    clauses_removed: int = 0
    clauses_modified: int = 0
    clauses_unchanged: int = 0

    # Risk comparison
    risk_summary: RiskSummary = field(default_factory=RiskSummary)


class ComparisonService:
    """Service for comparing document versions."""

    # Similarity threshold for considering clauses as "the same"
    SIMILARITY_THRESHOLD = 0.85

    # Similarity threshold for considering clauses as "modified" vs "different"
    MODIFICATION_THRESHOLD = 0.6

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

    async def compare_versions(
        self,
        version1_id: UUID,
        version2_id: UUID,
    ) -> Optional[ComparisonResult]:
        """Compare two document versions.

        Args:
            version1_id: ID of the first (older) version
            version2_id: ID of the second (newer) version

        Returns:
            ComparisonResult with all differences, or None if versions not found
        """
        # Fetch both versions with their clauses
        result1 = await self._get_version_with_clauses(version1_id)
        result2 = await self._get_version_with_clauses(version2_id)

        if not result1 or not result2:
            return None

        version1, clauses1 = result1
        version2, clauses2 = result2

        # Perform text-level diff
        text_diff = self._compute_text_diff(
            version1.extracted_text or "",
            version2.extracted_text or "",
        )

        # Perform clause-level comparison
        clause_changes = await self._compare_clauses(
            clauses1,
            clauses2,
        )

        # Calculate statistics
        added = sum(1 for c in clause_changes if c.change_type == ChangeType.ADDED)
        removed = sum(1 for c in clause_changes if c.change_type == ChangeType.REMOVED)
        modified = sum(1 for c in clause_changes if c.change_type == ChangeType.MODIFIED)
        unchanged = sum(1 for c in clause_changes if c.change_type == ChangeType.UNCHANGED)

        # Calculate risk summary
        risk_summary = self._compute_risk_summary(
            clauses1,
            clauses2,
            clause_changes,
        )

        return ComparisonResult(
            version1_id=version1_id,
            version2_id=version2_id,
            version1_number=version1.version_number,
            version2_number=version2.version_number,
            text_diff=text_diff,
            clause_changes=clause_changes,
            clauses_added=added,
            clauses_removed=removed,
            clauses_modified=modified,
            clauses_unchanged=unchanged,
            risk_summary=risk_summary,
        )

    async def _get_version_with_clauses(
        self, version_id: UUID
    ) -> Optional[tuple]:
        """Fetch a document version with its clauses.

        Returns:
            Tuple of (DocumentVersion, List[Clause]) or None
        """
        result = await self.db.execute(
            select(DocumentVersion).where(DocumentVersion.id == version_id)
        )
        version = result.scalar_one_or_none()

        if not version:
            return None

        # Fetch clauses separately to avoid lazy loading issues
        clause_result = await self.db.execute(
            select(Clause)
            .where(Clause.document_version_id == version_id)
            .order_by(Clause.start_position)
        )
        clauses = list(clause_result.scalars().all())

        return (version, clauses)

    def _compute_text_diff(self, text1: str, text2: str) -> TextDiff:
        """Compute text-level diff between two versions."""
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        differ = difflib.unified_diff(lines1, lines2, lineterm="")
        diff_lines = list(differ)

        # Count additions and deletions
        additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

        # Generate HTML diff for display
        html_diff = difflib.HtmlDiff()
        diff_html = html_diff.make_table(lines1, lines2, context=True, numlines=3)

        return TextDiff(
            additions=additions,
            deletions=deletions,
            diff_html=diff_html,
            diff_lines=diff_lines,
        )

    async def _compare_clauses(
        self,
        clauses1: List[Clause],
        clauses2: List[Clause],
    ) -> List[ClauseChange]:
        """Compare clauses between two versions using semantic similarity."""
        changes: List[ClauseChange] = []
        matched_new: set = set()

        for old_clause in clauses1:
            best_match: Optional[Tuple[Clause, float]] = None

            # Find best matching clause in new version
            for new_clause in clauses2:
                if new_clause.id in matched_new:
                    continue

                similarity = self._calculate_similarity(old_clause, new_clause)

                if similarity >= self.SIMILARITY_THRESHOLD:
                    if best_match is None or similarity > best_match[1]:
                        best_match = (new_clause, similarity)

            if best_match:
                new_clause, similarity = best_match
                matched_new.add(new_clause.id)

                if similarity >= 0.99:
                    # Essentially unchanged
                    changes.append(ClauseChange(
                        change_type=ChangeType.UNCHANGED,
                        clause_type=new_clause.clause_type,
                        new_clause_id=new_clause.id,
                        new_text=new_clause.text,
                        new_risk_level=new_clause.risk_level,
                        new_risk_score=new_clause.risk_score,
                        old_clause_id=old_clause.id,
                        old_text=old_clause.text,
                        old_risk_level=old_clause.risk_level,
                        old_risk_score=old_clause.risk_score,
                        similarity_score=similarity,
                    ))
                else:
                    # Modified
                    text_diff = self._generate_text_diff(old_clause.text, new_clause.text)
                    risk_change = self._calculate_risk_change(
                        old_clause.risk_score, new_clause.risk_score
                    )

                    changes.append(ClauseChange(
                        change_type=ChangeType.MODIFIED,
                        clause_type=new_clause.clause_type,
                        new_clause_id=new_clause.id,
                        new_text=new_clause.text,
                        new_risk_level=new_clause.risk_level,
                        new_risk_score=new_clause.risk_score,
                        old_clause_id=old_clause.id,
                        old_text=old_clause.text,
                        old_risk_level=old_clause.risk_level,
                        old_risk_score=old_clause.risk_score,
                        text_diff=text_diff,
                        similarity_score=similarity,
                        risk_change=risk_change,
                    ))
            else:
                # Check if there's a somewhat similar clause (modified significantly)
                best_partial: Optional[Tuple[Clause, float]] = None
                for new_clause in clauses2:
                    if new_clause.id in matched_new:
                        continue
                    similarity = self._calculate_similarity(old_clause, new_clause)
                    if similarity >= self.MODIFICATION_THRESHOLD:
                        if best_partial is None or similarity > best_partial[1]:
                            best_partial = (new_clause, similarity)

                if best_partial:
                    new_clause, similarity = best_partial
                    matched_new.add(new_clause.id)
                    text_diff = self._generate_text_diff(old_clause.text, new_clause.text)
                    risk_change = self._calculate_risk_change(
                        old_clause.risk_score, new_clause.risk_score
                    )

                    changes.append(ClauseChange(
                        change_type=ChangeType.MODIFIED,
                        clause_type=new_clause.clause_type,
                        new_clause_id=new_clause.id,
                        new_text=new_clause.text,
                        new_risk_level=new_clause.risk_level,
                        new_risk_score=new_clause.risk_score,
                        old_clause_id=old_clause.id,
                        old_text=old_clause.text,
                        old_risk_level=old_clause.risk_level,
                        old_risk_score=old_clause.risk_score,
                        text_diff=text_diff,
                        similarity_score=similarity,
                        risk_change=risk_change,
                    ))
                else:
                    # Removed
                    changes.append(ClauseChange(
                        change_type=ChangeType.REMOVED,
                        clause_type=old_clause.clause_type,
                        old_clause_id=old_clause.id,
                        old_text=old_clause.text,
                        old_risk_level=old_clause.risk_level,
                        old_risk_score=old_clause.risk_score,
                    ))

        # Find added clauses (in new but not matched)
        for new_clause in clauses2:
            if new_clause.id not in matched_new:
                changes.append(ClauseChange(
                    change_type=ChangeType.ADDED,
                    clause_type=new_clause.clause_type,
                    new_clause_id=new_clause.id,
                    new_text=new_clause.text,
                    new_risk_level=new_clause.risk_level,
                    new_risk_score=new_clause.risk_score,
                ))

        return changes

    def _calculate_similarity(self, clause1: Clause, clause2: Clause) -> float:
        """Calculate semantic similarity between two clauses."""
        if clause1.embedding is None or clause2.embedding is None:
            # Fallback to text similarity if no embeddings
            return difflib.SequenceMatcher(
                None, clause1.text, clause2.text
            ).ratio()

        return self.embedding_service.calculate_similarity(
            clause1.embedding, clause2.embedding
        )

    def _generate_text_diff(self, text1: str, text2: str) -> str:
        """Generate inline diff between two texts."""
        differ = difflib.ndiff(text1.split(), text2.split())
        return " ".join(differ)

    def _calculate_risk_change(
        self, old_score: float, new_score: float
    ) -> str:
        """Determine if risk increased, decreased, or stayed the same."""
        diff = new_score - old_score
        if diff > 0.1:
            return "increased"
        elif diff < -0.1:
            return "decreased"
        return "unchanged"

    def _compute_risk_summary(
        self,
        old_clauses: List[Clause],
        new_clauses: List[Clause],
        changes: List[ClauseChange],
    ) -> RiskSummary:
        """Compute overall risk change summary."""
        old_scores = [c.risk_score for c in old_clauses]
        new_scores = [c.risk_score for c in new_clauses]

        old_avg = sum(old_scores) / len(old_scores) if old_scores else 0.0
        new_avg = sum(new_scores) / len(new_scores) if new_scores else 0.0

        # Count critical/high changes
        critical_added = sum(
            1 for c in changes
            if c.change_type == ChangeType.ADDED and c.new_risk_level == "critical"
        )
        critical_removed = sum(
            1 for c in changes
            if c.change_type == ChangeType.REMOVED and c.old_risk_level == "critical"
        )
        high_added = sum(
            1 for c in changes
            if c.change_type == ChangeType.ADDED and c.new_risk_level == "high"
        )
        high_removed = sum(
            1 for c in changes
            if c.change_type == ChangeType.REMOVED and c.old_risk_level == "high"
        )

        # Determine trend
        diff = new_avg - old_avg
        if diff > 0.05:
            trend = "increased"
        elif diff < -0.05:
            trend = "decreased"
        else:
            trend = "unchanged"

        return RiskSummary(
            old_overall_score=round(old_avg, 3),
            new_overall_score=round(new_avg, 3),
            risk_trend=trend,
            critical_added=critical_added,
            critical_removed=critical_removed,
            high_risk_added=high_added,
            high_risk_removed=high_removed,
        )
