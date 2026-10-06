from pathlib import Path

from kube_triage.known_issues.loader import KnownIssueRegistry
from kube_triage.skills.loader import SkillRegistry

ROOT = Path(__file__).parents[1]


def test_skill_discovery_order() -> None:
    registry = SkillRegistry.load(ROOT / "skill-registry")

    assert not registry.errors
    assert len(registry.list_skills()) == 6
    assert registry.search("KubeDeploymentReplicasMismatch")[0].metadata.id == (
        "deployment/replica-mismatch"
    )
    assert registry.search("pods keep restarting")[0].metadata.id == (
        "deployment/crashloopbackoff"
    )
    assert len(registry.search("deployment", limit=20)) <= 2


def test_malformed_and_duplicate_skills_are_skipped(tmp_path: Path) -> None:
    source = ROOT / "skill-registry/deployment/replica-mismatch.md"
    content = source.read_text(encoding="utf-8")
    (tmp_path / "valid.md").write_text(content, encoding="utf-8")
    (tmp_path / "duplicate.md").write_text(content, encoding="utf-8")
    (tmp_path / "malformed.md").write_text("# No frontmatter", encoding="utf-8")

    registry = SkillRegistry.load(tmp_path)

    assert len(registry.list_skills()) == 1
    assert len(registry.errors) == 2


def test_known_issues_reference_valid_skills() -> None:
    skills = SkillRegistry.load(ROOT / "skill-registry")
    issues = KnownIssueRegistry.load(ROOT / "known-issues/catalog.yaml", skills)

    assert not issues.errors
    assert len(issues.list_issues()) == 3
    assert issues.search("metrics missing after rename")[0].id == "KI-001"
