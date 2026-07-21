#!/usr/bin/env python3
"""Score UI pipeline QA results and turn defects into focused retry guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IssueRule:
    dimension: str
    penalty: int
    instruction: str
    target: str = "production-sheet"


ISSUE_RULES: dict[str, IssueRule] = {
    "count-mismatch": IssueRule("count_accuracy", 45, "Generate exactly the requested number of resources in the declared row-major order."),
    "empty-slot": IssueRule("count_accuracy", 40, "Fill every declared slot with exactly one complete resource; do not leave any slot empty."),
    "cross-slot-connected-component": IssueRule("separation", 38, "Increase clean background separation and reduce each resource scale so no pixels connect across neighboring slots."),
    "canvas-edge-contact": IssueRule("framing", 34, "Keep every resource fully inside the canvas and add more clean background margin around the outer slots."),
    "multiple-major-components": IssueRule("separation", 28, "Draw one coherent main resource per slot; remove unrelated secondary objects and floating duplicates."),
    "detached-components": IssueRule("separation", 6, "Keep intentional ornaments visibly attached or close to their owning resource and remove unexplained floating fragments."),
    "visible-chroma-residue": IssueRule("alpha_cleanliness", 32, "Use a perfectly flat chroma background and prevent that key color from appearing in the resource, outline, glow, or reflection."),
    "visible-chroma-spill": IssueRule("alpha_cleanliness", 32, "Remove chroma-colored reflections and halos from the visible subject while keeping the background perfectly flat."),
    "near-key-subject-risk": IssueRule("alpha_cleanliness", 30, "Use the declared chroma key only for the background and recolor the subject away from that key and nearby hues."),
    "variable-chroma-border": IssueRule("alpha_cleanliness", 26, "Render one uniform chroma background with no gradient, texture, shadow, lighting variation, or compression noise."),
    "unsafe-adaptive-thresholds": IssueRule("alpha_cleanliness", 26, "Regenerate with a uniform high-contrast chroma background that is clearly separated from all subject colors."),
    "background-cleanup-failed": IssueRule("alpha_cleanliness", 30, "Regenerate on a single flat background color with no floor, cast shadow, reflection, gradient, or texture."),
    "source-matte-size-mismatch": IssueRule("matte_alignment", 40, "Edit the supplied color sheet into a grayscale alpha matte without changing canvas size, layout, scale, or pixel alignment.", "alpha-matte"),
    "source-matte-pixel-mismatch": IssueRule("matte_alignment", 40, "Derive the matte by editing the exact color sheet; preserve every silhouette and pixel position exactly.", "alpha-matte"),
    "model-matte-layering-lost": IssueRule("matte_alignment", 34, "Create a neutral grayscale matte with black transparent areas, white opaque cores, and continuous gray levels for soft transparency.", "alpha-matte"),
    "insufficient-partial-alpha-pixels": IssueRule("alpha_layering", 30, "Preserve meaningful partial transparency instead of collapsing the result to only fully transparent and fully opaque pixels.", "alpha-matte"),
    "insufficient-alpha-levels": IssueRule("alpha_layering", 30, "Preserve multiple continuous alpha levels for soft edges and translucent material."),
    "source-has-no-alpha-channel": IssueRule("alpha_layering", 40, "Provide a true RGBA PNG with a real alpha channel; do not bake transparency into RGB."),
    "source-has-no-transparent-pixels": IssueRule("alpha_layering", 36, "Provide a true RGBA source containing transparent background pixels."),
    "missing-native-alpha-provenance": IssueRule("provenance", 35, "Provide the required provenance sidecar for the exact RGBA source and its SHA-256.", "native-alpha-provenance"),
    "dimension-mismatch": IssueRule("dimensions", 32, "Preserve the requested output dimensions and aspect ratio exactly."),
    "empty-alpha": IssueRule("alpha_layering", 40, "Render a visible resource with non-empty alpha coverage."),
    "not-rgba": IssueRule("alpha_layering", 35, "Provide a true RGBA PNG instead of an opaque RGB image."),
    "no-transparent-padding": IssueRule("framing", 4, "Leave the requested transparent safety padding around the resource."),
    "cross-sheet-style-drift": IssueRule(
        "style_consistency",
        28,
        "Match the canonical palette, material, stroke language, contrast, and lighting direction used by the other production sheets; keep layout and resource semantics unchanged.",
    ),
    "panel-stretch-band-decoration": IssueRule(
        "nine_slice_safety",
        40,
        "Remove every unique ornament from the middle of all four Panel edges and rebuild plain continuous repeatable border lines; keep decoration only in the four fixed corners.",
    ),
    "button-stretch-band-decoration": IssueRule(
        "nine_slice_safety",
        40,
        "Remove every unique ornament from the middle of all four Button edges and rebuild plain continuous repeatable border lines; keep decoration only in the four fixed corners.",
    ),
}


def rule_for(code: str, severity: str) -> IssueRule:
    if code in ISSUE_RULES:
        return ISSUE_RULES[code]
    if "matte" in code:
        return IssueRule("matte_alignment", 30 if severity == "fail" else 5, "Regenerate the matte from the exact color sheet without changing layout or silhouettes.", "alpha-matte")
    if "alpha" in code:
        return IssueRule("alpha_layering", 28 if severity == "fail" else 4, "Preserve a valid transparent RGBA result with clean visible edges.")
    return IssueRule("other", 20 if severity == "fail" else 3, "Regenerate this job while fixing only the reported QA defect.")


def quality_status(score: int, hard_blockers: int) -> str:
    if hard_blockers:
        return "blocked"
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 60:
        return "fair"
    return "poor"


def evaluate_quality(
    qa_report: dict[str, Any],
    jobs: list[dict[str, Any]],
    assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    job_ids = [str(job["id"]) for job in jobs]
    job_issues: dict[str, list[dict[str, Any]]] = {job_id: [] for job_id in job_ids}
    global_issues: list[dict[str, Any]] = []
    dimensions: dict[str, dict[str, int]] = {}
    asset_ids = [str(asset.get("id", "")) for asset in (assets or []) if asset.get("id")]
    asset_issues: dict[str, list[dict[str, Any]]] = {asset_id: [] for asset_id in asset_ids}

    for issue in qa_report.get("issues", []):
        issue_copy = dict(issue)
        code = str(issue_copy.get("code", "unknown"))
        severity = str(issue_copy.get("severity", "warning"))
        rule = rule_for(code, severity)
        issue_copy["quality_dimension"] = rule.dimension
        issue_copy["quality_penalty"] = rule.penalty
        issue_copy["correction_instruction"] = rule.instruction
        issue_copy["retry_target"] = rule.target
        bucket = dimensions.setdefault(rule.dimension, {"issue_count": 0, "deduction": 0})
        bucket["issue_count"] += 1
        bucket["deduction"] += rule.penalty
        job_id = str(issue_copy.get("job_id", ""))
        if job_id in job_issues:
            job_issues[job_id].append(issue_copy)
        else:
            global_issues.append(issue_copy)
        asset_id = str(issue_copy.get("asset_id", ""))
        if asset_id in asset_issues:
            asset_issues[asset_id].append(issue_copy)

    job_scores: list[dict[str, Any]] = []
    for job_id in job_ids:
        issues = job_issues[job_id]
        deduction = sum(int(issue["quality_penalty"]) for issue in issues)
        blockers = sum(1 for issue in issues if issue.get("severity") == "fail")
        score = max(0, 100 - deduction)
        job_scores.append(
            {
                "id": job_id,
                "score": score,
                "status": quality_status(score, blockers),
                "hard_blocker_count": blockers,
                "issue_codes": [str(issue.get("code", "unknown")) for issue in issues],
            }
        )

    global_deduction = sum(int(issue["quality_penalty"]) for issue in global_issues)
    average = round(sum(item["score"] for item in job_scores) / len(job_scores)) if job_scores else 100
    score = max(0, average - global_deduction)
    hard_blockers = sum(1 for issue in qa_report.get("issues", []) if issue.get("severity") == "fail")
    asset_scores = []
    for asset_id in asset_ids:
        issues = asset_issues[asset_id]
        deduction = sum(int(issue["quality_penalty"]) for issue in issues)
        blockers = sum(1 for issue in issues if issue.get("severity") == "fail")
        asset_score = max(0, 100 - deduction)
        asset_scores.append(
            {
                "id": asset_id,
                "score": asset_score,
                "status": quality_status(asset_score, blockers),
                "hard_blocker_count": blockers,
                "issue_codes": [str(issue.get("code", "unknown")) for issue in issues],
            }
        )
    return {
        "schema_version": 1,
        "score": score,
        "status": quality_status(score, hard_blockers),
        "hard_blocker_count": hard_blockers,
        "dimensions": dimensions,
        "jobs": job_scores,
        "assets": asset_scores,
        "scoring_policy": "quality score ranks candidates only; any hard blocker still forbids formal delivery",
    }


def primary_issue(issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not issues:
        return None
    enriched = []
    for issue in issues:
        item = dict(issue)
        rule = rule_for(str(item.get("code", "unknown")), str(item.get("severity", "warning")))
        item["quality_dimension"] = rule.dimension
        item["quality_penalty"] = rule.penalty
        item["correction_instruction"] = rule.instruction
        item["retry_target"] = rule.target
        enriched.append(item)
    return max(
        enriched,
        key=lambda item: (
            item.get("severity") == "fail",
            int(item["quality_penalty"]),
            str(item.get("code", "")),
        ),
    )
