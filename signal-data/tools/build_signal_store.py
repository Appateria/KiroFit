#!/usr/bin/env python3
"""
Signal Intake -> Signal Store -> Signal Index for the Kiro Fit PSR.

Reads every raw source file under signal-data/0*-*/ and produces:

    signal-store/signals.jsonl      normalized records (psr.md schema + provenance fields)
    signal-store/signals.csv        flattened view for spreadsheets / SQL loading
    signal-store/rejections.jsonl   explicit rejection records with expiry
    signal-index/signal-index.csv   theme-level ranked view with factor breakdown
    signal-index/signal-index.json  same ranking for agent consumption
    signal-index/clusters.json      themes grouped into opportunity clusters

Scoring weights come from signal-index/scoring-config.yaml so the published numbers and
the documented model cannot diverge.

    python3 signal-data/tools/build_signal_store.py
"""

from __future__ import annotations

import csv
import json
import math
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 8, 27)
NAMESPACE = uuid.UUID("6f1c2a48-0d3b-4f2a-9c17-5f2e8b0a41d9")  # fixed -> deterministic ids

CFG = yaml.safe_load((ROOT / "signal-index" / "scoring-config.yaml").read_text())

# ---------------------------------------------------------------------------
# Reference maps
# ---------------------------------------------------------------------------

# NOTE: calorie-consumption themes (food_search_empty, barcode_scanner, recipes_meals,
# ai_photo_logging, portion_fidelity, edit_delete_missing, backdating_missing,
# meal_type_inference, pagination_missing, exercise_not_netted, macro_goals,
# water_tracking, guest_empty_dashboard) were retired from this dataset when the
# calorie feature was removed from ../src. Signals asserting that a non-existent
# feature is broken are noise, not signal. See README "Retired themes".

FEATURE_AREA = {
    "unit_system_imperial": "profile/units",
    "exercise_plan_generation": "exercise/planning",
    "progress_reports_periodic": "reports/periodic",
    "genai_charter": "platform/ai",
    "weight_trend_chart": "profile/analytics",
    "analytics_missing": "settings/premium",
    "data_export_missing": "settings/export",
    "billing_missing": "settings/subscription",
    "custom_activities": "exercise/log",
    "wearable_integration": "exercise/integrations",
    "history_latency": "exercise/history",
    "history_range_limit": "exercise/history",
    "guest_sync_loss": "auth/guest-sync",
    "guest_sync_duplicates": "auth/guest-sync",
    "guest_onboarding": "auth/guest-sync",
    "sso_required": "auth/enterprise",
    "admin_audit_log": "platform/enterprise",
    "gdpr_dsar": "platform/privacy",
    "public_profile_pii": "api/authorization",
    "server_validation_gap": "api/validation",
    "accessibility_a11y": "platform/accessibility",
    "dark_mode_contrast": "platform/theme",
    "offline_mode": "platform/offline",
    "reminders_missing": "platform/notifications",
    "streaks_gamification": "platform/engagement",
    "native_mobile_apps": "platform/mobile",
    "community_challenges": "community",
    "discover_stale_content": "discover/articles",
    "photo_upload_failure": "profile/photo",
    "error_messaging": "platform/ux",
    "observability_gap": "platform/observability",
    "instrumentation_gap": "platform/analytics",
    "dependency_currency": "platform/build",
    "ui_quality_positive": "platform/design",
    "deployability": "platform/deploy",
    "pricing_pressure": "settings/subscription",
}

CODE_REFS = {
    "unit_system_imperial": ["infra/graphql/schema.graphql:HealthProfile",
                             "ui/src/features/settings/components/HealthPreferencesSection.vue",
                             "ui/src/features/profile/pages/ProfileEditPage.vue"],
    "exercise_plan_generation": ["infra/graphql/schema.graphql:Mutation",
                                 "ui/src/features/exercise/pages/ExerciseDashboardPage.vue"],
    "progress_reports_periodic": ["infra/graphql/schema.graphql:Query.exerciseEntries",
                                  "ui/src/features/exercise/pages/ExerciseHistoryPage.vue"],
    "genai_charter": ["infra/lib/kirofit-stack.ts", "infra/graphql/schema.graphql:Mutation"],
    "weight_trend_chart": ["infra/graphql/schema.graphql:HealthProfile.weightKg"],
    "analytics_missing": ["ui/src/config/access.ts", "ui/src/features/settings/pages/SubscriptionPage.vue"],
    "data_export_missing": ["ui/src/config/access.ts:data-export"],
    "billing_missing": ["ui/src/features/settings/pages/SubscriptionPage.vue:handleUpgrade",
                        "ui/src/lib/auth/composables/useAccessTier.ts"],
    "guest_sync_loss": ["ui/src/composables/useGuestSync.ts:syncGuestDataToAccount"],
    "guest_sync_duplicates": ["ui/src/composables/useGuestSync.ts",
                              "infra/resolvers/mutation.logExercise.ts"],
    "history_latency": ["infra/resolvers/query.exerciseEntries.ts",
                        "ui/src/features/exercise/pages/ExerciseHistoryPage.vue"],
    "history_range_limit": ["infra/graphql/schema.graphql:Query.exerciseEntries"],
    "public_profile_pii": ["infra/graphql/schema.graphql:Query.profile", "infra/lib/constructs/api.ts"],
    "gdpr_dsar": ["infra/graphql/schema.graphql:Mutation"],
    "accessibility_a11y": ["ui/src/shared/components/StatGrid.vue",
                           "ui/src/features/exercise/components/WeeklySummary.vue"],
    "dark_mode_contrast": ["ui/src/theme/variables.css"],
    "offline_mode": ["ui/src/config/apollo.ts"],
    "photo_upload_failure": ["infra/lib/lambda/profile-photo/index.ts"],
    "sso_required": ["infra/lib/constructs/auth.ts"],
    "observability_gap": ["infra/lib/kirofit-stack.ts"],
    "instrumentation_gap": ["ui/src/features/exercise/pages/ExerciseDashboardPage.vue"],
    "dependency_currency": ["ui/package.json", "infra/package.json"],
    "server_validation_gap": ["infra/resolvers/mutation.logExercise.ts"],
    "error_messaging": ["ui/src/features/exercise/stores/exerciseStore.ts"],
    "discover_stale_content": ["ui/src/features/discover/services/articleService.ts"],
    "custom_activities": ["ui/src/features/exercise/types/exercise.ts:CustomActivityType"],
    "native_mobile_apps": ["ui/capacitor.config.ts"],
    "wearable_integration": ["ui/capacitor.config.ts"],
}

CLUSTERS = {
    "CL-01": ("Coach the plan, not just the log",
              ["exercise_plan_generation", "custom_activities"]),
    "CL-02": ("Let users own and correct their data",
              ["gdpr_dsar", "data_export_missing"]),
    "CL-03": ("Make progress legible",
              ["progress_reports_periodic", "weight_trend_chart", "analytics_missing"]),
    "CL-04": ("Stop losing data at sign-up",
              ["guest_sync_loss", "guest_sync_duplicates", "offline_mode", "guest_onboarding"]),
    "CL-05": ("Turn purchase intent into revenue",
              ["billing_missing", "pricing_pressure"]),
    "CL-06": ("Unblock the corporate wellness segment",
              ["sso_required", "admin_audit_log", "accessibility_a11y", "dark_mode_contrast"]),
    "CL-07": ("Query data the way users read it",
              ["history_latency", "history_range_limit"]),
    "CL-08": ("Operate the system we deployed",
              ["observability_gap", "instrumentation_gap", "dependency_currency", "server_validation_gap",
               "error_messaging", "photo_upload_failure", "public_profile_pii"]),
    "CL-09": ("Build an engagement loop",
              ["reminders_missing", "streaks_gamification", "discover_stale_content"]),
    "CL-10": ("Deferred and watch",
              ["native_mobile_apps", "community_challenges", "wearable_integration"]),
    "CL-11": ("Meet users in their own units",
              ["unit_system_imperial"]),
    "CL-12": ("Apply GenAI where it pays for itself",
              ["genai_charter"]),
    "CL-00": ("Strengths to protect", ["ui_quality_positive", "deployability"]),
}
THEME_CLUSTER = {t: cid for cid, (_, themes) in CLUSTERS.items() for t in themes}

# Intake classifier output for sources that carry no explicit theme column.
PFR_THEME = {
    "PFR-0321": "wearable_integration",
    "PFR-0327": "guest_sync_loss",
    "PFR-0334": "offline_mode", "PFR-0338": "billing_missing",
    "PFR-0347": "history_range_limit",
    "PFR-0352": "photo_upload_failure", "PFR-0359": "reminders_missing",
    "PFR-0363": "data_export_missing", "PFR-0368": "dark_mode_contrast",
    "PFR-0372": "custom_activities", "PFR-0379": "weight_trend_chart",
    "PFR-0385": "accessibility_a11y", "PFR-0391": "analytics_missing",
    "PFR-0398": "streaks_gamification",
    "PFR-0410": "sso_required", "PFR-0417": "native_mobile_apps",
    # Post-calorie-removal capability asks
    "PFR-0432": "unit_system_imperial", "PFR-0435": "exercise_plan_generation",
    "PFR-0441": "progress_reports_periodic", "PFR-0448": "unit_system_imperial",
    "PFR-0453": "exercise_plan_generation", "PFR-0457": "progress_reports_periodic",
}

CHURN_REASON_THEME = {
    "data_loss": "guest_sync_loss",
    "no_wearable_sync": "wearable_integration",
    "no_reporting": "progress_reports_periodic",
    "paid_for_missing_features": "analytics_missing",
    "offline_unusable": "offline_mode",
    "no_progress_view": "weight_trend_chart",
    "inaccessible": "accessibility_a11y",
    "forgot_to_use": "reminders_missing",
    "history_locked": "history_range_limit",
    "security_review_failed": "sso_required",
    "duplicate_data": "guest_sync_duplicates",
    "no_workout_guidance": "exercise_plan_generation",
    "wrong_units": "unit_system_imperial",
}

FLAKY_THEME = {
    "FLK-004": "history_latency",
    "FLK-005": "error_messaging", "FLK-006": "photo_upload_failure",
    "FLK-007": "offline_mode",
    "FLK-009": "guest_sync_loss",
    "FLK-011": "history_latency", "FLK-012": "billing_missing",
    "FLK-013": "accessibility_a11y", "FLK-014": "weight_trend_chart",
    "FLK-015": "offline_mode",
    "FLK-016": "unit_system_imperial", "FLK-017": "progress_reports_periodic",
}

REJECTED_THEMES = {
    "native_mobile_apps": ("NG1", "Web push covers the reminder use case at ~10% of the cost this "
                                  "quarter; signing, CI and store review are out of scope for FY26-Q3.",
                           "FY27-Q1", "two corporate accounts requiring wearable sync, or web-push "
                                      "reactivation lift holding past 60 days"),
    "community_challenges": ("NG3", "No in-product behavioral demand; enterprise buyers object to "
                                    "individual leaderboards on HR grounds.",
                             "FY27-Q2", "a privacy-preserving format validated with two program admins"),
}

MAPPED_THEMES = {
    "guest_sync_loss", "billing_missing", "history_latency", "history_range_limit",
    "sso_required", "data_export_missing", "accessibility_a11y", "dark_mode_contrast",
    "public_profile_pii", "gdpr_dsar",
    "unit_system_imperial", "exercise_plan_generation", "progress_reports_periodic",
}

PERSONA_BY_TIER = {
    "corporate_enterprise": "program_admin_enterprise",
    "corporate_smb": "program_admin_smb",
    "consumer_premium": "power_logger",
    "consumer_free": "casual_logger",
}

signals: list[dict] = []


def sid(source_ref: str) -> str:
    return str(uuid.uuid5(NAMESPACE, source_ref))


def add(cls, source, source_ref, raw, summary, theme, created_at,
        severity="medium", customer_tier="unknown", provenance="tier1_first_party_instrumentation",
        extra=None):
    if theme in (None, "", "n/a"):
        return
    signals.append({
        "signal_id": sid(source_ref),
        "class": cls,
        "source": source,
        "source_ref": source_ref,
        "raw_content": raw.strip()[:900],
        "normalized_summary": summary.strip(),
        "theme": theme,
        "entities": {
            "feature_area": FEATURE_AREA.get(theme, "unmapped"),
            "persona": PERSONA_BY_TIER.get(customer_tier, "internal" if cls == "strategic" else "unknown"),
            "severity_tag": severity,
            "cluster": THEME_CLUSTER.get(theme, "CL-99"),
        },
        "customer_tier": customer_tier,
        "created_at": created_at,
        "provenance_tier": provenance,
        "code_refs": CODE_REFS.get(theme, []),
        "weight": 0.0,
        "linked_signals": [],
        "status": "raw",
        **(extra or {}),
    })


def read_csv(rel):
    with (ROOT / rel).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_jsonl(rel):
    with (ROOT / rel).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def iso(d: str) -> str:
    """Normalize a date or datetime string to ISO8601 with a Z suffix."""
    d = d.strip()
    if not d:
        return "1970-01-01T00:00:00Z"
    if "T" in d:
        return d if d.endswith("Z") else d + "Z"
    return f"{d}T00:00:00Z"


def parse_day(iso_str: str) -> date:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).date()


# ---------------------------------------------------------------------------
# Intake — class 1: customer demand
# ---------------------------------------------------------------------------

def intake_customer_demand():
    for r in read_csv("01-customer-demand/zendesk-tickets.csv"):
        add("customer_demand", "zendesk", r["ticket_id"], r["verbatim"],
            f'Support ticket ({r["channel"]}): {r["subject"]}',
            r["theme"], iso(r["created_at"]), r["severity"], r["customer_tier"],
            "tier1_direct_customer",
            extra={"metrics": {"csat": int(r["csat"]) if r["csat"] else None,
                               "account_name": r["account_name"] or None}})

    for r in read_jsonl("01-customer-demand/product-feature-requests.jsonl"):
        theme = PFR_THEME.get(r["pfr_id"])
        sev = "high" if r["votes"] >= 400 else "medium" if r["votes"] >= 200 else "low"
        add("customer_demand", "in_product_pfr", r["pfr_id"],
            f'{r["title"]} — {r["body"]} [triage: {r["pm_note"]}]',
            f'Feature request ({r["votes"]} votes): {r["title"]}',
            theme, iso(r["submitted_at"]), sev, r["customer_tier"], "tier1_direct_customer",
            extra={"metrics": {"votes": r["votes"], "submitted_via": r["submitted_via"]}})

    for r in read_csv("01-customer-demand/nps-csat-verbatims.csv"):
        when = iso(r["surveyed_at"])
        score = r["nps_score"] or r["csat_score"]
        detractor = (r["nps_score"] and int(r["nps_score"]) <= 6) or (r["csat_score"] and int(r["csat_score"]) <= 2)
        for idx, theme in enumerate([r["primary_theme"], r["secondary_theme"]]):
            if not theme:
                continue
            add("customer_demand", "survey", f'{r["response_id"]}#{idx}', r["verbatim"],
                f'{r["survey"]} verbatim (score {score}, segment {r["segment"]}): '
                f'{r["verbatim"][:110]}',
                theme, when, "high" if detractor else "medium", r["customer_tier"],
                "tier1_direct_customer",
                extra={"metrics": {"nps": int(r["nps_score"]) if r["nps_score"] else None,
                                   "csat": int(r["csat_score"]) if r["csat_score"] else None}})

    for r in read_csv("01-customer-demand/churn-exit-surveys.csv"):
        theme = CHURN_REASON_THEME.get(r["primary_reason_code"])
        mrr = float(r["mrr_lost_usd"])
        add("customer_demand", "churn_survey", r["exit_id"], r["verbatim"],
            f'Churned after {r["tenure_days"]}d ({r["primary_reason_code"]}), '
            f'switched to {r["switched_to"]}',
            theme, iso(r["churned_at"]), "critical" if mrr > 100 else "high",
            r["customer_tier"], "tier1_direct_customer",
            extra={"metrics": {"mrr_lost_usd": mrr, "tenure_days": int(r["tenure_days"]),
                               "switched_to": r["switched_to"]}})

    for r in read_jsonl("01-customer-demand/app-store-reviews.jsonl"):
        sev = "high" if r["rating"] <= 2 else "medium" if r["rating"] == 3 else "low"
        tier = "consumer_premium" if "premium" in json.dumps(r).lower() else "consumer_free"
        for idx, theme in enumerate(r["themes"]):
            add("customer_demand", "app_store_review", f'{r["review_id"]}#{idx}',
                f'{r["title"]}: {r["body"]}',
                f'{r["store"]} review {r["rating"]}★ ({r["locale"]}): {r["title"]}',
                theme, iso(r["submitted_at"]), sev, tier, "tier1_direct_customer",
                extra={"metrics": {"rating": r["rating"], "helpful_count": r["helpful_count"]}})

    interviews = [
        ("INT-2026-014", "2026-06-11", "corporate_enterprise",
         ["sso_required", "data_export_missing", "admin_audit_log", "wearable_integration",
          "accessibility_a11y"],
         "Helios Health Systems discovery call: 4,200-seat expansion blocked on SSO and cohort "
         "reporting, with a VPAT required by 2026-12-01.", "critical"),
        ("INT-2026-021", "2026-07-14", "consumer_premium",
         ["exercise_plan_generation", "progress_reports_periodic", "unit_system_imperial",
          "streaks_gamification", "offline_mode", "history_range_limit"],
         "Power-user panel (n=6): all six wrote their own week's plan in a notes app and "
         "transcribed it in; 4 of 6 keep a parallel spreadsheet to see monthly totals; the two "
         "US panellists convert pounds in their head every session.", "high"),
    ]
    for ref, when, tier, themes, summary, sev in interviews:
        for idx, theme in enumerate(themes):
            add("customer_demand", "customer_interview", f"{ref}#{idx}", summary,
                f"Interview {ref}: {summary[:120]}", theme, iso(when), sev, tier,
                "tier1_direct_customer")


# ---------------------------------------------------------------------------
# Intake — class 2: defect & degradation
# ---------------------------------------------------------------------------

def intake_defects():
    sev_map = CFG["factors"]["severity"]["source_mappings"]
    for r in read_jsonl("02-defect-degradation/github-issues.jsonl"):
        add("defect", "github", f'GH-{r["number"]}', r["body"],
            f'Issue #{r["number"]}: {r["title"]}', r["theme"], iso(r["opened_at"]),
            sev_map.get(r["severity"], "medium"), "unknown",
            "tier1_first_party_instrumentation",
            extra={"metrics": {"comments": r["comments"],
                               "reactions": r["reactions"].get("+1", 0),
                               "labels": r["labels"]},
                   "code_refs": r.get("file_refs", [])})

    for r in read_jsonl("02-defect-degradation/sentry-frontend-errors.jsonl"):
        sev = {"error": "high", "warning": "medium", "info": "low"}[r["level"]]
        add("defect", "sentry", r["issue_id"], f'{r["title"]} @ {r["culprit"]}',
            f'{r["events"]:,} events / {r["users_affected"]:,} users: {r["title"]}',
            r["theme"], iso(r["last_seen"]), sev,
            "consumer_premium" if r["tags"].get("tier") == "premium" else "consumer_free",
            "tier1_first_party_instrumentation",
            extra={"metrics": {"events": r["events"], "users_affected": r["users_affected"],
                               "first_seen": r["first_seen"]}})

    for r in read_csv("02-defect-degradation/incident-log.csv"):
        add("defect", "incident_review", r["incident_id"], r["root_cause"],
            f'{r["severity"]} {r["title"]} — {r["users_affected"]} users, '
            f'MTTD {r["mttd_minutes"]}m',
            r["theme"], iso(r["opened_at"]), sev_map.get(r["severity"], "high"),
            "unknown", "tier1_first_party_instrumentation",
            extra={"metrics": {"users_affected": int(r["users_affected"]),
                               "mttd_minutes": int(r["mttd_minutes"]),
                               "detected_by": r["detected_by"]}})

    for r in read_csv("02-defect-degradation/flaky-tests.csv"):
        theme = FLAKY_THEME.get(r["test_id"])
        rate = float(r["flake_rate_pct"])
        add("defect", "ci_test_signal", r["test_id"], r["suspected_cause"],
            f'{r["suite"]} test flaking {rate}%: {r["test_name"]}',
            theme, iso(r["first_flaked"]),
            "high" if rate > 50 else "medium" if rate > 10 else "low",
            "unknown", "tier1_first_party_instrumentation",
            extra={"metrics": {"flake_rate_pct": rate, "quarantined": r["quarantined"] == "true"}})

    security = [
        ("PEN-2026-03-F01", "2026-06-12", "public_profile_pii", "high",
         "AppSync API key embedded in publicly served config.json."),
        ("PEN-2026-03-F02", "2026-06-12", "public_profile_pii", "high",
         "Query.profile exposes dob, location and bio to API-key callers with enumerable userId."),
        ("PEN-2026-03-F03", "2026-06-12", "public_profile_pii", "medium",
         "No field-level authorization: any authenticated user may read another user's profile."),
        ("PEN-2026-03-F04", "2026-06-12", "server_validation_gap", "medium",
         "Mutations perform no server-side validation; client zod bounds are the only limits."),
        ("PEN-2026-03-F05", "2026-06-12", "photo_upload_failure", "medium",
         "Presigned upload URL is unscoped by content-length; arbitrary-size object write."),
        ("PEN-2026-03-F07", "2026-06-12", "sso_required", "low",
         "Cognito password policy accepts 8 characters with no breach-list check."),
        ("PEN-2026-03-F08", "2026-06-12", "gdpr_dsar", "informational",
         "No account deletion or data-export path; erasure obligations unmet."),
        ("SEC-DEP-2026-08", "2026-08-24", "dependency_currency", "medium",
         "Reachable moderate advisory in axios 1.17.0; eslint 8 and Node 20 unsupported."),
        ("SEC-POSTURE-2026-08", "2026-08-01", "observability_gap", "high",
         "No CloudWatch alarms on AppSync 5xx or Lambda errors; MTTD 4.6 days."),
        ("SEC-POSTURE-2026-08b", "2026-08-01", "admin_audit_log", "medium",
         "CloudTrail data events disabled on the media bucket — no access trail for audit-log ask."),
        ("SEC-POSTURE-2026-08c", "2026-08-01", "photo_upload_failure", "low",
         "41GB of orphaned avatar objects from failed uploads; no lifecycle policy."),
        ("BB-2026-023", "2026-07-19", "photo_upload_failure", "medium",
         "Presigned URL reuse window allows re-upload after key rotation."),
        ("BB-2026-027", "2026-08-14", "public_profile_pii", "low",
         "Stored HTML in bio renders unescaped in the shared profile view."),
    ]
    for ref, when, theme, sev, summary in security:
        add("defect", "security_review", ref, summary, summary, theme, iso(when), sev,
            "unknown", "tier2_secondary_research")


# ---------------------------------------------------------------------------
# Intake — class 3: market & competitive
# ---------------------------------------------------------------------------

def intake_market():
    for r in read_jsonl("03-market-competitive/competitor-releases.jsonl"):
        sev = {"high": "high", "medium": "medium", "low": "low"}[r["confidence"]]
        add("market", "competitor_changelog", r["entry_id"],
            f'{r["competitor"]} {r["version"]}: {r["headline"]} — {r["detail"]}',
            f'{r["competitor"]} shipped: {r["headline"]}',
            r["threatens_theme"], iso(r["captured_at"]), sev, "unknown",
            "tier2_secondary_research",
            extra={"metrics": {"competitor": r["competitor"],
                               "kirofit_status": r["kirofit_status"],
                               "time_to_parity_weeks": r["time_to_parity_estimate_weeks"]}})

    for r in read_csv("03-market-competitive/tech-standards-watch.csv"):
        sev = "high" if r["action_window"] in ("expired", "90_days") else "medium"
        add("market", "tech_standards_watch", r["watch_id"],
            f'{r["item"]}: {r["event"]} (effective {r["effective_date"]}) — {r["impact"]}',
            f'{r["category"]}: {r["item"]} — {r["event"]}',
            r["theme"], iso(r["captured_at"]), sev, "unknown", "tier2_secondary_research",
            extra={"metrics": {"effective_date": r["effective_date"],
                               "action_window": r["action_window"],
                               "verification_status": r["verification_status"]}})

    matrix_gaps = [
        ("MTX-plan-generation", "exercise_plan_generation", "critical"),
        ("MTX-periodic-reports", "progress_reports_periodic", "critical"),
        ("MTX-unit-system", "unit_system_imperial", "critical"),
        ("MTX-ai-assist", "genai_charter", "high"),
        ("MTX-billing", "billing_missing", "critical"),
        ("MTX-weight-trend", "weight_trend_chart", "high"),
        ("MTX-history", "history_range_limit", "high"),
        ("MTX-export", "data_export_missing", "high"),
        ("MTX-analytics", "analytics_missing", "high"),
        ("MTX-a11y", "accessibility_a11y", "high"),
        ("MTX-wearable", "wearable_integration", "high"),
        ("MTX-sso", "sso_required", "high"),
        ("MTX-reminders", "reminders_missing", "medium"),
        ("MTX-streaks", "streaks_gamification", "medium"),
        ("MTX-custom-activities", "custom_activities", "medium"),
        ("MTX-native", "native_mobile_apps", "medium"),
        ("MTX-offline", "offline_mode", "medium"),
        ("MTX-guest-mode", "guest_onboarding", "low"),
        ("MTX-design", "ui_quality_positive", "low"),
        ("MTX-deploy", "deployability", "low"),
    ]
    for ref, theme, sev in matrix_gaps:
        add("market", "competitor_feature_matrix", ref,
            "Capability comparison against six category competitors "
            "(03-market-competitive/competitor-feature-matrix.csv).",
            f'Category comparison for {theme}: Kiro Fit gap severity {sev}',
            theme, iso("2026-08-20"), sev, "unknown", "tier2_secondary_research")

    analyst = [
        ("MKT-ANALYST-014#1", "exercise_plan_generation", "critical",
         "Analyst note: prescription, not recording, is the retention variable in the category "
         "(r≈0.68 with W4). Five of six tracked vendors now generate a plan; a log-only product "
         "is priced as a commodity."),
        ("MKT-ANALYST-014#2", "progress_reports_periodic", "high",
         "Analyst note: a periodic progress readout is the most-cited reason users describe a "
         "tracker as 'worth paying for'; weekly and monthly are the only two periods that matter."),
        ("MKT-ANALYST-014#6", "genai_charter", "high",
         "Analyst note: vendors shipping generated plans and narrative summaries are doing so on "
         "managed foundation models at $0.01–0.05 per active user per month, well inside the "
         "margin of a consumer subscription. Building equivalent rule engines is the more "
         "expensive path at this scale."),
        ("MKT-ANALYST-014#7", "unit_system_imperial", "high",
         "Analyst note: the US is ~63% of category revenue and every tracked competitor offers "
         "imperial units; metric-only entry is a conversion blocker, not a preference."),
        ("MKT-ANALYST-014#3", "billing_missing", "high",
         "Analyst note: category free tiers are widening while price points rise; Kiro Fit has "
         "no revenue instrument at all."),
        ("MKT-ANALYST-014#4", "sso_required", "high",
         "Analyst note: retained revenue in the category is employer-sponsored, gated on SSO, "
         "reporting, accessibility and a security attestation."),
        ("MKT-ANALYST-014#5", "guest_onboarding", "low",
         "Analyst note: browse-before-signup is a genuine category differentiator, currently "
         "undermined by a lossy sign-up sync."),
        ("MKT-REG-2026-08#1", "gdpr_dsar", "high",
         "Regulatory watch: access, erasure and rectification rights are all unmet; erasure is "
         "currently actioned by ad-hoc DynamoDB deletes."),
        ("MKT-REG-2026-08#2", "accessibility_a11y", "high",
         "Regulatory watch: accessibility conformance is becoming a procurement gate; a VPAT is "
         "required by 2026-12-01 for the Helios expansion."),
        ("MKT-REG-2026-08#3", "analytics_missing", "high",
         "Regulatory watch: advertising six unimplemented premium benefits creates a "
         "deceptive-practice exposure if charging begins."),
        ("MKT-REG-2026-08#4", "billing_missing", "medium",
         "Regulatory watch: web checkout avoids store commission and needs no native launch."),
    ]
    for ref, theme, sev, summary in analyst:
        when = "2026-08-12" if ref.startswith("MKT-ANALYST") else "2026-08-20"
        add("market", "analyst_report" if ref.startswith("MKT-ANALYST") else "regulatory_watch",
            ref, summary, summary, theme, iso(when), sev, "unknown", "tier2_secondary_research")


# ---------------------------------------------------------------------------
# Intake — class 4: usage & behavioral
# ---------------------------------------------------------------------------

def intake_behavioral():
    for r in read_jsonl("04-usage-behavioral/ab-test-results.jsonl"):
        sev = "high" if r["decision"] in ("ship_blocked", "no_ship") else "medium"
        for idx, theme in enumerate(r["themes"]):
            add("behavioral", "ab_test", f'{r["experiment_id"]}#{idx}',
                f'{r["hypothesis"]} Decision: {r["decision"]} — {r["decision_note"]}',
                f'{r["experiment_id"]} {r["name"]}: {r["lift_pct"]:+.1f}% on '
                f'{r["primary_metric"]} ({r["decision"]})',
                theme, iso(r["started"]), sev, "unknown", "tier1_first_party_instrumentation",
                extra={"metrics": {"lift_pct": r["lift_pct"], "p_value": r["p_value"],
                                   "decision": r["decision"], "status": r["status"]}})

    # Derived aggregates, computed from the generated telemetry files.
    # Help-centre search: unanswered queries are demand signals, grouped by the
    # theme they imply. The product has no search surface of its own.
    searches = read_csv("04-usage-behavioral/help-center-search-terms.csv")
    by_hint: dict[str, list[dict]] = defaultdict(list)
    for r in searches:
        if r["theme_hint"] and int(r["zero_result_searches"]) > 0:
            by_hint[r["theme_hint"]].append(r)
    for hint, rows in sorted(by_hint.items()):
        q = sum(int(r["searches"]) for r in rows)
        terms = sorted({r["query"] for r in rows})
        add("behavioral", "help_center_search", f"BEH-helpsearch-{hint}",
            f'Help-centre search log: {q:,} unanswered searches across {len(rows)} distinct '
            f'terms ({", ".join(terms[:4])}{"..." if len(terms) > 4 else ""}). The help centre '
            f'has no article because the product has no such capability.',
            f'{q:,} help-centre searches across {len(rows)} terms ask for a capability that '
            f'does not exist',
            hint, iso("2026-08-26"),
            "critical" if q >= 12000 else "high" if q >= 4000 else "medium",
            "unknown", "tier1_first_party_instrumentation",
            extra={"metrics": {"searches": q, "distinct_terms": len(rows),
                               "example_terms": terms[:6]}})

    add("behavioral", "product_analytics", "BEH-instrumentation-gap",
        "Plan-adherence and report-demand analysis both required help-centre log archaeology; "
        "the product emits no event for an unmet capability request.",
        "Key product surfaces emit no analytics events, so unmet demand is only visible by "
        "reconstructing help-centre and support logs",
        "instrumentation_gap", iso("2026-08-12"), "medium", "unknown",
        "tier1_first_party_instrumentation")

    funnels = read_csv("04-usage-behavioral/funnel-dropoff-weekly.csv")
    hard_zero = defaultdict(list)
    for r in funnels:
        if r["note"].startswith("hard zero") and int(r["users"]) == 0:
            hard_zero[r["step"]].append(r["funnel"])
    zero_theme = {
        "checkout_started": ("billing_missing", "critical"),
        "subscription_active": ("billing_missing", "critical"),
        "range_change_succeeded": ("history_range_limit", "high"),
        "report_export_attempted": ("progress_reports_periodic", "critical"),
    }
    for step, funnel_names in hard_zero.items():
        theme, sev = zero_theme[step]
        add("behavioral", "product_analytics", f"BEH-funnel-zero-{step}",
            f'Funnel step "{step}" converted 0 users across all 21 measured weeks in '
            f'{sorted(set(funnel_names))[0]}.',
            f'Funnel step "{step}" never fires — the code path does not exist',
            theme, iso("2026-08-26"), sev, "unknown", "tier1_first_party_instrumentation",
            extra={"metrics": {"weeks_measured": 21, "conversions": 0}})

    add("behavioral", "product_analytics", "BEH-retention-history-cohort",
        "Cohort analysis from cohort-retention-weekly.csv: users who opened history in week 1 "
        "retain at ~35% by W4 versus ~21% for users who only logged, and ~11% for users whose "
        "sessions were verbatim repeats of the previous one.",
        "Looking back at progress predicts retention far better than logging does — the reporting "
        "surface is the retention lever, and users who have nothing to follow churn fastest",
        "progress_reports_periodic", iso("2026-08-26"), "high", "consumer_free",
        "tier1_first_party_instrumentation",
        extra={"metrics": {"w4_retention_history_cohort_pct": 35,
                           "w4_retention_log_only_cohort_pct": 21,
                           "w4_retention_repeat_session_cohort_pct": 11}})

    add("behavioral", "product_analytics", "BEH-session-repetition",
        "exercise_logging_session funnel: repeat_of_previous_session runs at 71.2% across all 21 "
        "measured weeks; repeat_previous_session events carry plan_source=null and up to 9 "
        "consecutive identical sessions.",
        "71% of logged sessions are verbatim repeats of the previous one — users have no plan to "
        "progress against",
        "exercise_plan_generation", iso("2026-08-26"), "critical", "consumer_free",
        "tier1_first_party_instrumentation",
        extra={"metrics": {"repeat_rate_pct": 71.2, "max_consecutive_repeats": 9}})

    add("behavioral", "product_analytics", "BEH-unit-entry-anomaly",
        "profile_unit_confusion: weightKg and heightCm values that are only plausible as pounds, "
        "feet or inches (e.g. 154 'kg', 5.9 'cm') are written unconverted to the health profile.",
        "Users in imperial locales enter imperial numbers into metric-only fields, so stored body "
        "metrics are silently wrong",
        "unit_system_imperial", iso("2026-08-26"), "high", "consumer_free",
        "tier1_first_party_instrumentation")

    add("behavioral", "product_analytics", "BEH-guest-sync-leak",
        "guest_to_first_log funnel: 12.1% of guest sessions complete sign-up but only 7.4% end "
        "with a successful guest-data sync; every guest_sync_partial_failure event carries "
        "local_cache_cleared=true.",
        "~39% of successfully signed-up guests lose some or all of their pre-signup entries",
        "guest_sync_loss", iso("2026-08-26"), "critical", "consumer_free",
        "tier1_first_party_instrumentation",
        extra={"metrics": {"signup_completed_pct": 12.1, "synced_ok_pct": 7.4}})

    add("behavioral", "product_analytics", "BEH-upgrade-intent-deadend",
        "upgrade_placeholder_toast_shown: 14,203 events from 9,877 distinct users over the window.",
        "9,877 distinct users expressed purchase intent into a placeholder toast",
        "billing_missing", iso("2026-08-26"), "critical", "consumer_free",
        "tier1_first_party_instrumentation",
        extra={"metrics": {"distinct_users": 9877, "events": 14203}})

    add("behavioral", "product_analytics", "BEH-history-render",
        "history_opened events carry queries_issued=7 and render_ms up to 9,600; 31.1% of history "
        "views are abandoned before render.",
        "Exercise history week view issues 7 queries and is abandoned 31% of the time before render",
        "history_latency", iso("2026-08-26"), "high", "consumer_free",
        "tier1_first_party_instrumentation",
        extra={"metrics": {"queries_per_view": 7, "abandon_pct": 31.1, "p95_render_ms": 8940}})

    add("behavioral", "product_analytics", "BEH-report-range-deadend",
        "history_view funnel: 39.8% of history sessions attempt a range change and 0 succeed "
        "across all 21 measured weeks; report_export_attempted also converts to zero, with "
        "requested_period split between 1w and 1m.",
        "Two in five history sessions ask for a different period and none can get one; the "
        "requested periods are exactly one week and one month",
        "progress_reports_periodic", iso("2026-08-26"), "critical", "consumer_free",
        "tier1_first_party_instrumentation",
        extra={"metrics": {"range_change_attempt_pct": 39.8, "conversions": 0,
                           "weeks_measured": 21}})

    add("behavioral", "product_analytics", "BEH-adoption-decline",
        "feature-adoption-daily.csv: exercise_log and exercise_history both decline across the "
        "window while the dashboard entry point holds.",
        "Logging surfaces are decaying fastest while the dashboard entry point holds — users open "
        "the app, see the same numbers as last week, and leave",
        "progress_reports_periodic", iso("2026-08-26"), "high", "consumer_free",
        "tier1_first_party_instrumentation")

    add("behavioral", "product_analytics", "BEH-discover-decay",
        "discover_list DAU share declining with no new content since 2026-07-01 (MOCK_ARTICLES).",
        "Discover tab traffic decaying against static bundled content",
        "discover_stale_content", iso("2026-08-26"), "low", "consumer_free",
        "tier1_first_party_instrumentation")

    errs = read_csv("02-defect-degradation/appsync-error-rates-daily.csv")
    log_before = [float(r["error_rate_pct"]) for r in errs
                  if r["operation"].startswith("Mutation.log") and parse_day(iso(r["date"])) < date(2026, 6, 18)]
    log_after = [float(r["error_rate_pct"]) for r in errs
                 if r["operation"].startswith("Mutation.log") and parse_day(iso(r["date"])) >= date(2026, 6, 18)]
    step = (sum(log_after) / len(log_after)) / (sum(log_before) / len(log_before))
    add("behavioral", "product_analytics", "BEH-logmutation-error-step",
        f'Mean logExercise error rate rose from '
        f'{sum(log_before) / len(log_before):.2f}% to {sum(log_after) / len(log_after):.2f}% '
        f'({step:.1f}x) on release r-1.0.14, 2026-06-18.',
        f'Logging mutation error rate stepped {step:.1f}x after r-1.0.14, matching the guest-sync '
        f'ticket cluster',
        "guest_sync_loss", iso("2026-06-18"), "high", "consumer_free",
        "tier1_first_party_instrumentation",
        extra={"metrics": {"error_rate_step_multiple": round(step, 2)}})


# ---------------------------------------------------------------------------
# Intake — class 5: strategic & business
# ---------------------------------------------------------------------------

def intake_strategic():
    okrs = yaml.safe_load((ROOT / "05-strategic-business/okrs-fy26.yaml").read_text())
    theme_alignment: dict[str, float] = {}
    theme_okrs: dict[str, set[str]] = defaultdict(set)

    for obj in okrs["objectives"]:
        w = float(obj["alignment_weight"])
        for kr in obj["key_results"]:
            sev = {"at_risk": "high", "not_started": "medium", "on_track": "low"}.get(kr["status"], "medium")
            for theme in kr.get("blocked_by_themes", []):
                theme_alignment[theme] = max(theme_alignment.get(theme, 0.0), w)
                theme_okrs[theme].add(kr["id"])
                add("strategic", "okr", f'{kr["id"]}#{theme}',
                    f'{obj["title"]} / {kr["statement"]} (baseline {kr["baseline"]}, '
                    f'target {kr["target"]}, status {kr["status"]})',
                    f'{kr["id"]} blocked by {theme}: {kr["statement"]}',
                    theme, iso("2026-07-01"), sev, "unknown", "tier1_direct_customer",
                    extra={"metrics": {"objective": obj["id"], "kr_status": kr["status"],
                                       "alignment_weight": w}})

    non_goal_themes = set()
    for ng in okrs["non_goals"]:
        for theme in ng["themes"]:
            non_goal_themes.add(theme)
            theme_alignment[theme] = CFG["factors"]["strategic_alignment"]["non_goal_value"]
            add("strategic", "okr_non_goal", f'{ng["id"]}#{theme}', ng["reason"],
                f'Declared non-goal {ng["id"]}: {ng["statement"]} (revisit {ng["revisit"]})',
                theme, iso("2026-07-01"), "low", "unknown", "tier1_direct_customer",
                extra={"metrics": {"revisit": ng["revisit"]}})

    effort_days: dict[str, int] = {}
    for r in read_csv("05-strategic-business/tech-debt-register.csv"):
        days = int(r["remediation_estimate_days"])
        sev = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}[r["interest_rate"]]
        for theme in [t for t in r["blocks_themes"].split(";") if t]:
            effort_days[theme] = min(effort_days.get(theme, 999), days)
            add("strategic", "tech_debt_register", f'{r["debt_id"]}#{theme}',
                f'{r["title"]} @ {r["location"]} — risk if deferred: {r["risk_if_deferred"]}',
                f'{r["debt_id"]} ({r["category"]}, interest {r["interest_rate"]}): {r["title"]}',
                theme, iso(r["recorded_at"]), sev, "unknown",
                "tier1_first_party_instrumentation",
                extra={"metrics": {"remediation_estimate_days": days,
                                   "blast_radius": r["blast_radius"],
                                   "debt_status": r["status"]}})

    for r in read_csv("05-strategic-business/partnership-commitments.csv"):
        value = float(r["contract_value_usd_annual"])
        sev = "critical" if r["status"] == "at_risk" and value >= 10000 else \
              "high" if r["status"] in ("at_risk", "negotiating") else "medium"
        tier = "corporate_enterprise" if value >= 10000 else \
               "corporate_smb" if value > 0 else "unknown"
        for theme in [t for t in r["dependent_themes"].split(";") if t]:
            add("strategic", "partnership_commitment", f'{r["commitment_id"]}#{theme}',
                f'{r["partner"]}: {r["obligation"]} (due {r["delivery_due"]}) — '
                f'risk: {r["penalty_or_risk"]}',
                f'{r["commitment_id"]} {r["partner"]} ({r["type"]}, ${value:,.0f}/yr, '
                f'{r["status"]}) depends on {theme}',
                theme, iso(r["signed_at"]), sev, tier, "tier1_direct_customer",
                extra={"metrics": {"contract_value_usd_annual": value,
                                   "delivery_due": r["delivery_due"],
                                   "commitment_status": r["status"]}})

    pricing = [
        ("STRAT-PRICING#1", "billing_missing", "critical",
         "No revenue instrument exists: every packaging decision is theoretical until checkout "
         "and an entitlement store exist. Stride Payments integration slot expires 2026-09-30."),
        ("STRAT-PRICING#2", "gdpr_dsar", "high",
         "Packaging constraint: rectification cannot sit behind a paywall, so correcting or "
         "removing an activity record must ship on the free tier."),
        ("STRAT-PRICING#6", "progress_reports_periodic", "high",
         "Packaging boundary: the weekly report is the free-tier retention hook; the monthly "
         "report with trend narrative and export is the premium unit. Splitting by period rather "
         "than by capability keeps the free tier honest."),
        ("STRAT-PRICING#7", "genai_charter", "high",
         "Packaging constraint: generated plans and report narratives carry a marginal inference "
         "cost per user, so they cannot sit on an unmetered free tier. Free gets one plan "
         "generation per month; premium gets unlimited regeneration."),
        ("STRAT-PRICING#8", "unit_system_imperial", "medium",
         "Packaging constraint: unit preference is an accessibility-adjacent basic, never a paid "
         "feature."),
        ("STRAT-PRICING#3", "data_export_missing", "high",
         "Packaging constraint: a user's own-data export is an access right (free); the employer's "
         "cohort report is a corporate-plan feature."),
        ("STRAT-PRICING#4", "exercise_plan_generation", "medium",
         "Packaging constraint: competitors put a basic generated plan on their free tiers, so "
         "plan generation itself cannot be the paywall — plan depth and revision can be."),
        ("STRAT-PRICING#5", "analytics_missing", "high",
         "SubscriptionPage advertises six premium benefits, zero implemented; benefits list should "
         "be derived from shipped capability."),
        ("STRAT-ADR-010", "genai_charter", "critical",
         "ADR-010: adopt generative/agentic AI as the default implementation strategy wherever it "
         "is the cost-effective route to customer value, on a managed foundation model, with a "
         "documented cost/benefit and a deterministic fallback per capability. First two "
         "applications are plan generation and report narration."),
        ("STRAT-ADR-010b", "exercise_plan_generation", "critical",
         "ADR-010 applied: generate plans from profile plus history through a managed model rather "
         "than hand-authoring a template library — ~6 engineer-days versus ~30, and the template "
         "library would need curation forever."),
        ("STRAT-ADR-011", "progress_reports_periodic", "high",
         "ADR-011: periodic reports aggregate server-side over the health single table and require "
         "a range query on the EXERCISE# sort key. The narrative layer is generated; the numbers "
         "are computed deterministically and never by the model."),
        ("STRAT-ADR-007", "offline_mode", "high",
         "ADR-007: scope a local draft/outbox with idempotency keys rather than an offline-first "
         "rewrite; unblocks EXP-2026-007 and removes the guest-sync loss mechanism."),
        ("STRAT-ADR-004", "native_mobile_apps", "low",
         "ADR-004: web-first distribution retained; native shells configured but unused, so "
         "HealthKit/Health Connect remain structurally unavailable."),
        ("STRAT-ADR-009", "observability_gap", "high",
         "ADR-009 proposal: alarms become part of the definition of done for any new resolver, "
         "starting with the range-query resolver."),
        ("STRAT-ADR-001", "unit_system_imperial", "high",
         "ADR-001: one combined schema means the unit-preference field, weight history, range "
         "queries and the plan/report types all land in the same weekly schema review — batch "
         "them rather than paying the review cost five times."),
        ("STRAT-ADR-008", "dependency_currency", "medium",
         "ADR-008 proposal: no dependency more than one major behind and no EOL runtime in "
         "production; ~8 engineer-days of upgrade work competes with feature work."),
    ]
    for ref, theme, sev, summary in pricing:
        add("strategic", "internal_decision_record", ref, summary, summary, theme,
            iso("2026-08-25"), sev, "unknown", "tier1_direct_customer")

    return theme_alignment, effort_days, non_goal_themes, theme_okrs


# ---------------------------------------------------------------------------
# Intake — class 6: ambient & ecosystem
# ---------------------------------------------------------------------------

def intake_ambient():
    for r in read_jsonl("06-ambient-ecosystem/social-listening.jsonl"):
        sev = {"high": "medium", "medium": "low", "low": "informational"}[r["signal_strength"]]
        for idx, theme in enumerate(r["themes"]):
            add("ambient", f'social_{r["platform"]}', f'{r["mention_id"]}#{idx}', r["excerpt"],
                f'{r["platform"]}/{r["community"]} ({r["sentiment"]}): {r["excerpt"][:110]}',
                theme, iso(r["captured_at"]), sev, "unknown", "tier3_ambient_unverified",
                extra={"metrics": {"engagement": r["engagement"],
                                   "brand_mentioned": r["brand_mentioned"]}})

    for r in read_jsonl("06-ambient-ecosystem/competitor-job-postings.jsonl"):
        sev = {"high": "medium", "medium": "low", "low": "informational"}[r["confidence"]]
        for idx, theme in enumerate(r["themes"]):
            add("ambient", "job_posting", f'{r["posting_id"]}#{idx}',
                f'{r["company"]} hiring {r["count_open"]}x {r["title"]}: '
                f'{", ".join(r["excerpt_keywords"])}. Inference: {r["roadmap_inference"]}',
                f'{r["company"]} hiring for {theme}: {r["roadmap_inference"]}',
                theme, iso(r["captured_at"]), sev, "unknown", "tier3_ambient_unverified",
                extra={"metrics": {"roles_open": r["count_open"], "company": r["company"]}})

    for r in read_csv("06-ambient-ecosystem/oss-momentum.csv"):
        sev = {"rising": "low", "steady": "informational", "flat": "informational"}[r["momentum"]]
        add("ambient", "oss_momentum", f'OSS-{r["repo"].replace("/", "-")}',
            f'{r["repo"]} ({r["momentum"]}, +{r["star_velocity_30d"]} stars/30d): '
            f'{r["relevance_to_kirofit"]} — {r["note"]}',
            f'Ecosystem option for {r["inferred_theme"]}: {r["repo"]} ({r["momentum"]})',
            r["inferred_theme"], iso("2026-08-25"), sev, "unknown", "tier3_ambient_unverified",
            extra={"metrics": {"stars": int(r["stars"]),
                               "star_velocity_30d": int(r["star_velocity_30d"]),
                               "momentum": r["momentum"]}})

    community = [
        ("AMB-HN-THREAD", "deployability", "low",
         "Hacker News thread (242 points): the deployment architecture is a reputational asset "
         "among developers while the product surface is the liability."),
        ("AMB-HN-THREAD#2", "ui_quality_positive", "informational",
         "Design quality praised in 17 of 118 HN comments and in most negative app-store reviews."),
        ("AMB-REDDIT-VELOCITY", "exercise_plan_generation", "medium",
         "August r/fitness thread introduces a new ambient signal: 'abandoned-looking'. Four months "
         "of unchanged behaviour is now itself the signal, and the top reply is that the app "
         "'never tells you what to do next'."),
        ("AMB-DISCORD-PRACTITIONERS", "sso_required", "medium",
         "Two corporate wellness program managers running pilots both expect procurement to block "
         "on SSO."),
        ("AMB-DISCORD-GUEST", "guest_onboarding", "low",
         "Practitioner view: guest-first onboarding is the design idea worth copying, and the "
         "sign-up sync failure is why nobody has copied it."),
        ("AMB-OSS-AXE", "accessibility_a11y", "low",
         "axe-core plus a Cypress gate is the cheapest route to the accessibility KR, and the "
         "existing a11y-dashboard spec already fails 98% of runs."),
        ("AMB-HIRING-ROLLUP", "genai_charter", "medium",
         "Across the tracked competitor postings nobody is hiring for interface craft; spend is on "
         "applied-ML/LLM roles, data access, integrations and enterprise gates. Two competitors "
         "are explicitly hiring for 'workout plan generation' and 'coaching LLM' work."),
        ("AMB-DISCORD-COST", "genai_charter", "low",
         "Practitioner Discord: teams shipping generated plans report $0.01–0.03 per active user "
         "per month on managed models, and all of them keep a static fallback plan for outages."),
    ]
    for ref, theme, sev, summary in community:
        add("ambient", "community_sweep", ref, summary, summary, theme, iso("2026-08-25"),
            sev, "unknown", "tier3_ambient_unverified")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score(theme_alignment, effort_days, non_goal_themes, theme_okrs):
    f = CFG["factors"]
    sev_values = f["severity"]["values"]
    tier_values = f["customer_tier"]["values"]
    half_life = f["recency"]["half_life_days"]
    corr = {int(k): v for k, v in CFG["corroboration"]["multipliers"].items()}
    kinds = CFG["theme_kinds"]

    by_theme = defaultdict(list)
    for s in signals:
        by_theme[s["theme"]].append(s)

    index = []
    theme_weight = {}

    for theme, group in by_theme.items():
        classes = sorted({s["class"] for s in group})
        sources = sorted({s["source"] for s in group})
        dates = [parse_day(s["created_at"]) for s in group]
        last, first = max(dates), min(dates)

        freq = 0.6 * min(1.0, len(sources) / 8) + 0.4 * min(1.0, len(group) / 40)
        recency = 0.5 ** ((TODAY - last).days / half_life)
        tier = max(tier_values.get(s["customer_tier"], tier_values["unknown"]) for s in group)
        sev = max(sev_values.get(s["entities"]["severity_tag"], 0.3) for s in group)
        align = theme_alignment.get(theme, f["strategic_alignment"]["default_unmapped"])
        eff = (1 - min(effort_days[theme], 30) / 30) if theme in effort_days \
            else f["effort_inverse"]["default_unknown"]

        base = (f["frequency"]["weight"] * freq
                + f["recency"]["weight"] * recency
                + f["customer_tier"]["weight"] * tier
                + f["severity"]["weight"] * sev
                + f["strategic_alignment"]["weight"] * align
                + f["effort_inverse"]["weight"] * eff)
        multiplier = corr[min(len(classes), 6)]
        weight = base * multiplier / max(corr.values())
        theme_weight[theme] = weight

        kind = "strength" if theme in kinds["strength"] else \
               "context" if theme in kinds["context"] else "gap"
        status = "rejected" if theme in REJECTED_THEMES else \
                 "mapped" if theme in MAPPED_THEMES else "processed"

        index.append({
            "theme": theme,
            "kind": kind,
            "cluster": THEME_CLUSTER.get(theme, "CL-99"),
            "feature_area": FEATURE_AREA.get(theme, "unmapped"),
            "status": status,
            "signal_count": len(group),
            "class_count": len(classes),
            "classes": "|".join(classes),
            "distinct_sources": len(sources),
            "sources": "|".join(sources),
            "first_seen": first.isoformat(),
            "last_reinforced": last.isoformat(),
            "days_since_reinforced": (TODAY - last).days,
            "frequency_score": round(freq, 3),
            "recency_score": round(recency, 3),
            "customer_tier_score": round(tier, 3),
            "severity_score": round(sev, 3),
            "strategic_alignment_score": round(align, 3),
            "effort_inverse_score": round(eff, 3),
            "effort_estimate_days": effort_days.get(theme, ""),
            "base_score": round(base, 4),
            "corroboration_multiplier": multiplier,
            "weight": round(weight, 4),
            "okr_refs": "|".join(sorted(theme_okrs.get(theme, []))),
            "code_refs": "|".join(CODE_REFS.get(theme, [])),
            "top_source_refs": "|".join(s["source_ref"] for s in
                                        sorted(group, key=lambda x: x["created_at"], reverse=True)[:5]),
        })

    index.sort(key=lambda r: -r["weight"])
    for rank, row in enumerate(index, 1):
        row["rank"] = rank

    # Per-signal weight, status and corroboration links.
    for theme, group in by_theme.items():
        w = theme_weight[theme]
        by_class = defaultdict(list)
        for s in group:
            by_class[s["class"]].append(s)
        for s in group:
            r = 0.5 ** ((TODAY - parse_day(s["created_at"])).days / half_life)
            s["weight"] = round(w * (0.7 + 0.3 * r), 3)
            s["status"] = "rejected" if theme in REJECTED_THEMES else \
                          "mapped" if theme in MAPPED_THEMES else "processed"
            links = []
            for cls, members in by_class.items():
                if cls == s["class"]:
                    continue
                links.append(max(members, key=lambda x: x["created_at"])["signal_id"])
            s["linked_signals"] = sorted(links)[:4]

    return index


def build_rejections():
    by_theme = defaultdict(list)
    for s in signals:
        by_theme[s["theme"]].append(s)
    out = []
    for theme, (ng, reason, revisit, trigger) in REJECTED_THEMES.items():
        group = by_theme.get(theme, [])
        out.append({
            "rejection_id": f"REJ-{theme}",
            "theme": theme,
            "non_goal_ref": ng,
            "signal_ids": [s["signal_id"] for s in group],
            "signal_count": len(group),
            "affected_source_refs": [s["source_ref"] for s in group][:12],
            "reason": reason,
            "decided_by": "pm_rowan",
            "decided_at": "2026-07-01T00:00:00Z",
            "expires_at": "2026-12-28T00:00:00Z",
            "expiry_behaviour": "re-enters scoring with full weight on expiry",
            "revisit_quarter": revisit,
            "revisit_trigger": trigger,
            "status": "rejected",
        })
    # Solution-shape rejections. The parent theme stays active and keeps its rank;
    # only the tested implementation is rejected. This is the RFC-0001 §5.1
    # outcome-feedback amendment: an experiment result changes a record's status
    # without discarding the underlying demand.
    out.append({
        "rejection_id": "REJ-EXP-2026-041",
        "theme": "exercise_plan_generation",
        "non_goal_ref": None,
        "signal_ids": [sid("EXP-2026-041#0")],
        "signal_count": 1,
        "affected_source_refs": ["EXP-2026-041"],
        "reason": "Static starter plan card rejected as the shipping shape: it lifted W2 return "
                  "11.4% and cut verbatim session repeats from 71% to 58%, then 34% of treatment "
                  "users abandoned the plan by week 3 because it cannot adapt. The demand is "
                  "confirmed; a fixed plan is not the answer to it.",
        "decided_by": "pm_rowan",
        "decided_at": "2026-08-05T00:00:00Z",
        "expires_at": "2027-02-05T00:00:00Z",
        "expiry_behaviour": "solution-shape rejection only; parent theme stays in the index",
        "revisit_quarter": "n/a",
        "revisit_trigger": "a generated plan that adapts on logged adherence (ADR-010b)",
        "status": "rejected_solution_shape",
    })
    out.append({
        "rejection_id": "REJ-EXP-2026-044",
        "theme": "progress_reports_periodic",
        "non_goal_ref": None,
        "signal_ids": [sid("EXP-2026-044#0")],
        "signal_count": 1,
        "affected_source_refs": ["EXP-2026-044"],
        "reason": "Client-side aggregation rejected as the shipping shape: engagement lift was "
                  "real (+9.1% weekly return visits, p=0.014) but p95 render hit 11.2s across the "
                  "7-query fan-out and 28% abandoned before render. Stopped on performance, not "
                  "on demand — the theme is rank 1.",
        "decided_by": "perf_owner",
        "decided_at": "2026-08-10T00:00:00Z",
        "expires_at": "2027-02-10T00:00:00Z",
        "expiry_behaviour": "solution-shape rejection only; parent theme stays in the index",
        "revisit_quarter": "n/a",
        "revisit_trigger": "re-run after the range-query resolver lands (GH-557, ADR-011)",
        "status": "rejected_solution_shape",
    })
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(index, rejections):
    store = ROOT / "signal-store"
    store.mkdir(exist_ok=True)
    idx_dir = ROOT / "signal-index"
    idx_dir.mkdir(exist_ok=True)

    ordered = sorted(signals, key=lambda s: (s["created_at"], s["source_ref"]))

    with (store / "signals.jsonl").open("w", encoding="utf-8") as fh:
        for s in ordered:
            fh.write(json.dumps(s, separators=(",", ":")) + "\n")
    print(f"wrote signal-store/signals.jsonl ({len(ordered)} records)")

    cols = ["signal_id", "class", "source", "source_ref", "theme", "cluster", "feature_area",
            "persona", "severity_tag", "customer_tier", "created_at", "provenance_tier",
            "weight", "status", "linked_signal_count", "normalized_summary"]
    with (store / "signals.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for s in ordered:
            w.writerow([s["signal_id"], s["class"], s["source"], s["source_ref"], s["theme"],
                        s["entities"]["cluster"], s["entities"]["feature_area"],
                        s["entities"]["persona"], s["entities"]["severity_tag"],
                        s["customer_tier"], s["created_at"], s["provenance_tier"],
                        s["weight"], s["status"], len(s["linked_signals"]),
                        s["normalized_summary"]])
    print(f"wrote signal-store/signals.csv ({len(ordered)} rows)")

    with (store / "rejections.jsonl").open("w", encoding="utf-8") as fh:
        for r in rejections:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(f"wrote signal-store/rejections.jsonl ({len(rejections)} records)")

    idx_cols = ["rank", "theme", "kind", "cluster", "feature_area", "status", "weight",
                "corroboration_multiplier", "base_score", "class_count", "classes",
                "signal_count", "distinct_sources", "sources", "frequency_score",
                "recency_score", "customer_tier_score", "severity_score",
                "strategic_alignment_score", "effort_inverse_score", "effort_estimate_days",
                "first_seen", "last_reinforced", "days_since_reinforced", "okr_refs",
                "code_refs", "top_source_refs"]
    with (idx_dir / "signal-index.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=idx_cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(index)
    print(f"wrote signal-index/signal-index.csv ({len(index)} themes)")

    (idx_dir / "signal-index.json").write_text(json.dumps({
        "generated_at": TODAY.isoformat(),
        "scoring_config_version": CFG["version"],
        "signal_count": len(signals),
        "theme_count": len(index),
        "themes": index,
    }, indent=2) + "\n", encoding="utf-8")
    print("wrote signal-index/signal-index.json")

    by_theme_row = {r["theme"]: r for r in index}
    clusters = []
    for cid, (title, themes) in CLUSTERS.items():
        rows = [by_theme_row[t] for t in themes if t in by_theme_row]
        if not rows:
            continue
        clusters.append({
            "cluster_id": cid,
            "title": title,
            "theme_count": len(rows),
            "signal_count": sum(r["signal_count"] for r in rows),
            "max_theme_weight": max(r["weight"] for r in rows),
            "mean_theme_weight": round(sum(r["weight"] for r in rows) / len(rows), 4),
            "classes_represented": sorted({c for r in rows for c in r["classes"].split("|")}),
            "themes": [{"theme": r["theme"], "rank": r["rank"], "weight": r["weight"],
                        "status": r["status"], "class_count": r["class_count"]} for r in
                       sorted(rows, key=lambda r: -r["weight"])],
        })
    clusters.sort(key=lambda c: -c["max_theme_weight"])
    (idx_dir / "clusters.json").write_text(json.dumps({
        "generated_at": TODAY.isoformat(),
        "clusters": clusters,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote signal-index/clusters.json ({len(clusters)} clusters)")

    print("\nTop 15 by weight:")
    for r in index[:15]:
        print(f'  {r["rank"]:>2}. {r["weight"]:.3f}  x{r["corroboration_multiplier"]:.2f}  '
              f'{r["class_count"]} classes  {r["signal_count"]:>3} signals  '
              f'{r["theme"]:<24} [{r["status"]}]')


def main():
    intake_customer_demand()
    intake_defects()
    intake_market()
    intake_behavioral()
    alignment, effort, non_goals, theme_okrs = intake_strategic()
    intake_ambient()
    index = score(alignment, effort, non_goals, theme_okrs)
    write_outputs(index, build_rejections())


if __name__ == "__main__":
    main()
