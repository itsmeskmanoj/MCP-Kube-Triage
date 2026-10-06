import logging
import re
from pathlib import Path

import yaml
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from kube_triage.models import KnownIssue
from kube_triage.skills.loader import SkillRegistry

logger = logging.getLogger(__name__)
_WORD = re.compile(r"[a-z0-9]+")


class KnownIssueRegistry:
    def __init__(self, issues: dict[str, KnownIssue], errors: list[str] | None = None) -> None:
        self._issues = issues
        self.errors = errors or []

    @classmethod
    def load(cls, path: Path, skills: SkillRegistry) -> "KnownIssueRegistry":
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            parsed = TypeAdapter(list[KnownIssue]).validate_python(raw)
        except (OSError, yaml.YAMLError, PydanticValidationError) as exc:
            message = f"Known-issue catalog could not be loaded: {exc}"
            logger.error(message)
            return cls({}, [message])

        issues: dict[str, KnownIssue] = {}
        errors: list[str] = []
        for issue in parsed:
            if issue.id in issues:
                errors.append(f"duplicate known-issue id: {issue.id}")
                continue
            if skills.read(issue.skill_id) is None:
                errors.append(
                    f"known issue {issue.id} references missing skill {issue.skill_id}"
                )
                continue
            issues[issue.id] = issue
        for error in errors:
            logger.error(error)
        return cls(issues, errors)

    def list_issues(self) -> list[KnownIssue]:
        return [self._issues[issue_id] for issue_id in sorted(self._issues)]

    def search(self, query: str, *, limit: int = 2) -> list[KnownIssue]:
        words = set(_WORD.findall(query.casefold()))
        if not words or limit < 1:
            return []
        ranked: list[tuple[int, str, KnownIssue]] = []
        for issue in self._issues.values():
            text = " ".join([issue.title, issue.summary, *issue.signals]).casefold()
            score = len(words & set(_WORD.findall(text)))
            if score:
                ranked.append((score, issue.id, issue))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked[: min(limit, 2)]]
