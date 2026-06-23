from __future__ import annotations

from typing import Any

from core.io import now_iso


PLACEHOLDER_TOKENS = (
    "待定义",
    "待完善",
    "placeholder",
    "TODO",
    "{{",
    "}}",
    "<待",
    "未命名",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


class PlaceholderDetector:
    """Detect placeholder tokens in generated planning text."""

    def detect(self, text: str) -> list[str]:
        """Return all placeholder tokens present in text."""
        haystack = _text(text)
        lower = haystack.lower()
        return [token for token in PLACEHOLDER_TOKENS if token.lower() in lower]


class IntelligentReviewer:
    """Review program and art requirements for actionable quality issues."""

    def __init__(self) -> None:
        self.placeholder_detector = PlaceholderDetector()

    def review_program(self, requirements: list[dict[str, Any]]) -> dict[str, Any]:
        """Review Step 03 program requirements."""
        issues: list[dict[str, Any]] = []
        placeholder_count = 0
        l4_derived_count = 0
        if not requirements:
            issues.append(
                self._issue(
                    "BLOCKER",
                    "stage_03",
                    "program_requirements_contract.json",
                    "requirements",
                    "No program requirements were produced.",
                    "Run Step 03 after design handoff.",
                )
            )
        for requirement in requirements:
            req_id = _text(requirement.get("id"))
            self._check_trace(
                issues,
                "stage_03",
                "program_requirements_contract.json",
                req_id,
                requirement.get("source_refs"),
            )
            if not requirement.get("system_ids") and not self._is_project_configuration_requirement(
                requirement
            ):
                issues.append(
                    self._issue(
                        "WARNING",
                        "stage_03",
                        "program_requirements_contract.json",
                        req_id,
                        "Requirement is not bound to a system.",
                        "Bind by dependency id or fuzzy system match.",
                    )
                )
            if self._check_placeholder(
                issues,
                "stage_03",
                "program_requirements_contract.json",
                req_id,
                requirement.get("requirement"),
            ):
                placeholder_count += 1
            if self._is_l4_derived_requirement(requirement):
                l4_derived_count += 1
            self._check_requirement_depth(
                issues, "stage_03", "program_requirements_contract.json", req_id, requirement
            )
            for field in ("inputs", "outputs", "dependencies"):
                if field not in requirement:
                    issues.append(
                        self._issue(
                            "INFO",
                            "stage_03",
                            "program_requirements_contract.json",
                            f"{req_id}.{field}",
                            f"Requirement has no `{field}` field.",
                            f"Populate `{field}` for execution planning.",
                        )
                    )
            if not requirement.get("acceptance"):
                issues.append(
                    self._issue(
                        "CRITICAL",
                        "stage_03",
                        "program_requirements_contract.json",
                        req_id,
                        "Requirement has no acceptance criteria.",
                        "Add a concrete acceptance statement.",
                    )
                )
        if l4_derived_count:
            issues.append(
                self._issue(
                    "WARNING",
                    "stage_03",
                    "program_requirements_contract.json",
                    "requirement_depth",
                    f"{l4_derived_count} requirements appear to come from L4 design decisions.",
                    "Fill in L5 entities to generate more implementation-level requirements.",
                )
            )
        if requirements and placeholder_count / len(requirements) > 0.5:
            issues.append(
                self._issue(
                    "BLOCKER",
                    "stage_03",
                    "program_requirements_contract.json",
                    "placeholder_rate",
                    "More than 50% of requirements contain placeholder text.",
                    "Regenerate Step 03 from concrete design entities before planning.",
                )
            )
        return self._report("program_requirements", issues)

    def review_art(self, assets: list[dict[str, Any]]) -> dict[str, Any]:
        """Review Step 04 art requirements."""
        issues: list[dict[str, Any]] = []
        if not assets:
            issues.append(
                self._issue(
                    "BLOCKER",
                    "stage_04",
                    "asset_registry.json",
                    "assets",
                    "No art assets were produced.",
                    "Run Step 04 after design handoff.",
                )
            )
        for asset in assets:
            asset_id = _text(asset.get("asset_id"))
            self._check_trace(
                issues,
                "stage_04",
                "asset_registry.json",
                asset_id,
                [asset.get("source")] if asset.get("source") else [],
            )
            for field in ("asset_type", "purpose", "priority"):
                if not asset.get(field):
                    issues.append(
                        self._issue(
                            "WARNING",
                            "stage_04",
                            "asset_registry.json",
                            f"{asset_id}.{field}",
                            f"Asset has no `{field}`.",
                            f"Populate `{field}` for production planning.",
                        )
                    )
            self._check_placeholder(
                issues, "stage_04", "asset_registry.json", asset_id, asset.get("purpose")
            )
        if assets:
            self._check_asset_type_coverage(issues, "stage_04", "asset_registry.json", assets)
            self._check_p0_asset_count(issues, "stage_04", "asset_registry.json", assets)
        return self._report("art_requirements", issues)

    def _check_trace(
        self,
        issues: list[dict[str, Any]],
        stage: str,
        artifact: str,
        item_id: str,
        sources: Any,
    ) -> None:
        """Add a traceability issue when source references are missing."""
        if not sources:
            issues.append(
                self._issue(
                    "CRITICAL",
                    stage,
                    artifact,
                    item_id,
                    "Item has no source trace.",
                    "Keep source refs from design selection or L5 entity.",
                )
            )

    def _check_placeholder(
        self,
        issues: list[dict[str, Any]],
        stage: str,
        artifact: str,
        item_id: str,
        text: Any,
    ) -> bool:
        """Add a critical issue when text still contains placeholders."""
        tokens = self.placeholder_detector.detect(_text(text))
        if tokens:
            issues.append(
                self._issue(
                    "CRITICAL",
                    stage,
                    artifact,
                    item_id,
                    f"Placeholder tokens remain: {', '.join(tokens)}.",
                    "Replace template text with concrete design-driven content.",
                )
            )
            return True
        return False

    def _check_requirement_depth(
        self,
        issues: list[dict[str, Any]],
        stage: str,
        artifact: str,
        req_id: str,
        requirement: dict[str, Any],
    ) -> None:
        """Add warnings for shallow or L4-derived requirement text."""
        text = _text(requirement.get("requirement"))
        if len(text) < 15:
            issues.append(
                self._issue(
                    "WARNING",
                    stage,
                    artifact,
                    req_id,
                    "Requirement text is too short to describe meaningful behavior.",
                    "Expand the requirement with structure, behavior, and acceptance.",
                )
            )

    def _check_asset_type_coverage(
        self,
        issues: list[dict[str, Any]],
        stage: str,
        artifact: str,
        assets: list[dict[str, Any]],
    ) -> None:
        """Add critical issues when core asset types are missing."""
        present = {_text(asset.get("asset_type")) for asset in assets}
        for missing_type in sorted({"ui", "effect", "environment"} - present):
            issues.append(
                self._issue(
                    "CRITICAL",
                    stage,
                    artifact,
                    "asset_types",
                    f"No assets of type `{missing_type}` found.",
                    f"Generate {missing_type} assets by adding relevant L5 entities.",
                )
            )

    def _check_p0_asset_count(
        self,
        issues: list[dict[str, Any]],
        stage: str,
        artifact: str,
        assets: list[dict[str, Any]],
    ) -> None:
        """Add a warning when no critical-path P0 assets exist."""
        if not any(asset.get("priority") == "P0" for asset in assets):
            issues.append(
                self._issue(
                    "WARNING",
                    stage,
                    artifact,
                    "p0_assets",
                    "No P0 priority assets defined.",
                    "Mark critical-path assets such as character, weapon, core UI, or VFX as P0.",
                )
            )

    def _is_project_configuration_requirement(self, requirement: dict[str, Any]) -> bool:
        """Return true for L1 project configuration requirements exempt from system binding."""
        combined = " ".join(
            _text(requirement.get(key))
            for key in ("requirement", "entity_label", "entity_kind", "entity_schema", "phase")
        )
        project_tokens = ("项目规模", "商业模式", "平台范围", "地区范围", "项目定位", "社交模式")
        return any(token in combined for token in project_tokens)

    def _is_l4_derived_requirement(self, requirement: dict[str, Any]) -> bool:
        """Return true when a requirement still reflects L4 design-decision wording."""
        text = _text(requirement.get("requirement"))
        return any(token in text for token in ("范本反推", "项目配置", "设计决策节点"))

    def _issue(
        self,
        severity: str,
        stage: str,
        artifact: str,
        field: str,
        reason: str,
        suggestion: str,
    ) -> dict[str, str]:
        """Build one normalized review issue."""
        return {
            "severity": severity,
            "stage": stage,
            "artifact": artifact,
            "field": field,
            "reason": reason,
            "suggestion": suggestion,
        }

    def _report(self, scope: str, issues: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a normalized review report with verdict and severity counts."""
        counts = {severity: 0 for severity in ("BLOCKER", "CRITICAL", "WARNING", "INFO")}
        for issue in issues:
            severity = issue.get("severity", "INFO")
            counts[severity] = counts.get(severity, 0) + 1
        blocker_count = counts.get("BLOCKER", 0)
        critical_count = counts.get("CRITICAL", 0)
        warning_count = counts.get("WARNING", 0)
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "scope": scope,
            "verdict": self._verdict(blocker_count, critical_count, warning_count),
            "issues": issues,
            "severity_counts": counts,
            "blocker_count": blocker_count,
            "critical_count": critical_count,
            "requires_action_count": blocker_count + critical_count,
            "blocking_issue_count": blocker_count,
            "warning_count": warning_count,
        }

    def _verdict(self, blocker_count: int, critical_count: int, warning_count: int) -> str:
        """Return PASS, WARN, FAIL, or BLOCKED from severity counts."""
        if blocker_count:
            return "BLOCKED"
        if critical_count:
            return "FAIL"
        if warning_count > 0:
            return "WARN"
        return "PASS"
