from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from kube_triage.known_issues.loader import KnownIssueRegistry
from kube_triage.models import ErrorComponent, ToolResultEnvelope
from kube_triage.skills.loader import SkillRegistry
from kube_triage.tools.common import error_result

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def register_knowledge_tools(
    server: FastMCP,
    skills: SkillRegistry,
    known_issues: KnownIssueRegistry,
) -> None:
    @server.tool(annotations=_READ_ONLY)
    def search_skills(query: str) -> ToolResultEnvelope:
        """Find at most two skills and sanitized known issues for a symptom or code."""
        try:
            matched_skills = skills.search(query, limit=2)
            matched_issues = known_issues.search(query, limit=2)
            return ToolResultEnvelope.success(
                {
                    "skills": [
                        skill.summary().model_dump(mode="json")
                        for skill in matched_skills
                    ],
                    "known_issues": [
                        issue.model_dump(mode="json") for issue in matched_issues
                    ],
                }
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.KNOWLEDGE)

    @server.tool(annotations=_READ_ONLY)
    def get_skill_index() -> ToolResultEnvelope:
        """Return a compact index of all valid operational skills."""
        try:
            loaded = skills.list_skills()
            return ToolResultEnvelope.success(
                {
                    "skills": [
                        skill.summary().model_dump(mode="json") for skill in loaded
                    ],
                    "count": len(loaded),
                    "skipped_count": len(skills.errors),
                }
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.KNOWLEDGE)

    @server.tool(annotations=_READ_ONLY)
    def read_skill(skill_id: str) -> ToolResultEnvelope:
        """Read one operational skill by its stable category/name ID."""
        try:
            skill = skills.read(skill_id)
            if skill is None:
                return ToolResultEnvelope.failure(
                    ErrorComponent.KNOWLEDGE,
                    "skill_not_found",
                    "No valid skill matched the supplied stable ID",
                )
            return ToolResultEnvelope.success(
                {
                    "skill": skill.summary().model_dump(mode="json"),
                    "markdown": skill.markdown,
                }
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.KNOWLEDGE)
