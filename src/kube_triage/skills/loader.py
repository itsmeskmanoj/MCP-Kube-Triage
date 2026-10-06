import logging
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from kube_triage.models import SkillSummary

logger = logging.getLogger(__name__)
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
_WORD = re.compile(r"[a-z0-9]+")


class SkillMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
    category: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = Field(min_length=10)
    difficulty: str
    tags: list[str] = Field(min_length=1)
    tools_required: list[str] = Field(min_length=1)
    codes: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(min_length=1)
    tier: str
    est_tokens: int = Field(ge=1, le=20_000)


class Skill:
    def __init__(self, metadata: SkillMetadata, markdown: str, source: Path) -> None:
        self.metadata = metadata
        self.markdown = markdown
        self.source = source

    @property
    def uri(self) -> str:
        return f"skill://kube-triage/{self.metadata.id}"

    def summary(self) -> SkillSummary:
        return SkillSummary(
            id=self.metadata.id,
            name=self.metadata.name,
            category=self.metadata.category,
            description=self.metadata.description,
            difficulty=self.metadata.difficulty,
            tags=self.metadata.tags,
            codes=self.metadata.codes,
            triggers=self.metadata.triggers,
            tier=self.metadata.tier,
            est_tokens=self.metadata.est_tokens,
            uri=self.uri,
        )


class SkillRegistry:
    def __init__(self, skills: dict[str, Skill], errors: list[str] | None = None) -> None:
        self._skills = skills
        self.errors = errors or []

    @classmethod
    def load(cls, root: Path) -> "SkillRegistry":
        skills: dict[str, Skill] = {}
        errors: list[str] = []
        if not root.exists():
            message = f"Skill registry directory does not exist: {root}"
            logger.error(message)
            return cls({}, [message])

        for path in sorted(root.rglob("*.md")):
            try:
                skill = cls._load_file(path)
                if skill.metadata.id in skills:
                    raise ValueError(f"duplicate skill id: {skill.metadata.id}")
                if skill.metadata.id.split("/", maxsplit=1)[0] != skill.metadata.category:
                    raise ValueError("skill id category does not match category")
            except (OSError, ValueError, yaml.YAMLError, PydanticValidationError) as exc:
                message = f"Skipping malformed skill {path}: {exc}"
                logger.error(message)
                errors.append(message)
                continue
            skills[skill.metadata.id] = skill
        return cls(skills, errors)

    @staticmethod
    def _load_file(path: Path) -> Skill:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        match = _FRONTMATTER.match(text)
        if not match:
            raise ValueError("missing YAML frontmatter")
        raw_metadata, body = match.groups()
        parsed = yaml.safe_load(raw_metadata)
        if not isinstance(parsed, dict):
            raise ValueError("frontmatter must be a mapping")
        metadata = SkillMetadata.model_validate(parsed)
        if not body.lstrip().startswith("# "):
            raise ValueError("skill body must start with a level-one heading")
        return Skill(metadata, text, path)

    def list_skills(self) -> list[Skill]:
        return [self._skills[skill_id] for skill_id in sorted(self._skills)]

    def read(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def search(self, query: str, *, limit: int = 2) -> list[Skill]:
        normalized = query.casefold().strip()
        if not normalized or limit < 1:
            return []
        query_words = set(_WORD.findall(normalized))
        ranked: list[tuple[int, str, Skill]] = []
        for skill in self._skills.values():
            score = self._score(skill, normalized, query_words)
            if score > 0:
                ranked.append((score, skill.metadata.id, skill))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked[: min(limit, 2)]]

    def search_many(self, queries: list[str], *, limit: int = 2) -> list[Skill]:
        matches: list[Skill] = []
        seen: set[str] = set()
        for query in queries:
            for skill in self.search(query, limit=2):
                if skill.metadata.id not in seen:
                    seen.add(skill.metadata.id)
                    matches.append(skill)
                if len(matches) == min(limit, 2):
                    return matches
        return matches

    @staticmethod
    def _score(skill: Skill, query: str, query_words: set[str]) -> int:
        codes = [code.casefold() for code in skill.metadata.codes]
        if query in codes:
            return 1000
        if any(code in query for code in codes):
            return 900

        triggers = [trigger.casefold() for trigger in skill.metadata.triggers]
        if query in triggers:
            return 800
        if any(trigger in query or query in trigger for trigger in triggers):
            return 700

        searchable = " ".join(
            [
                skill.metadata.name,
                skill.metadata.description,
                skill.metadata.category,
                *skill.metadata.tags,
            ]
        ).casefold()
        overlap = query_words & set(_WORD.findall(searchable))
        return len(overlap) * 10
