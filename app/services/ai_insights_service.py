"""Prepare a bounded local report for the optional AI Coach."""

from __future__ import annotations

from typing import Any

from app.services.dashboard_service import DashboardService
from app.services.daily_progress_service import DailyProgressService
from app.services.daily_reflection_service import DailyReflectionService
from app.services.stats_service import StatsService
from app.utils import time_utils


class AiInsightsService:
    """Build JSON-ready recent facts without contacting an AI provider."""

    def __init__(
        self,
        dashboard: DashboardService,
        progress: DailyProgressService,
        reflections: DailyReflectionService,
        stats: StatsService,
    ) -> None:
        self.dashboard = dashboard
        self.progress = progress
        self.reflections = reflections
        self.stats = stats

    def recent_report(self, days: int = 14) -> dict[str, Any]:
        """Return the last ``days`` of data, including zero-activity days."""
        days = max(3, min(int(days), 31))
        end_date = time_utils.today_str()
        start_date = time_utils.add_days(end_date, -(days - 1))
        period = self.stats.period_stats(start_date, end_date, label="AI review")
        reflections = self.reflections.list_by_date_range(start_date, end_date)

        daily: list[dict[str, Any]] = []
        active_days = 0
        scored_days = 0
        for offset in range(days):
            date = time_utils.add_days(start_date, offset)
            summary = self.dashboard.build_summary(date)
            score = self.progress.score(date)
            if summary.recorded_minutes:
                active_days += 1
            goal_score: int | None = None
            if score.has_scored_categories:
                goal_score = round(score.average_pct)
                scored_days += 1
            daily.append(
                {
                    "date": date,
                    "productive_minutes": summary.productive_minutes,
                    "recorded_minutes": summary.recorded_minutes,
                    "sessions": summary.session_count,
                    "goal_score_percent": goal_score,
                }
            )

        return {
            "window": {"start": start_date, "end": end_date, "days": days},
            "period_summary": {
                "productive_minutes": period.total_productive_minutes,
                "recorded_minutes": period.total_recorded_minutes,
                "active_days": active_days,
                "sessions": period.session_count,
                "average_session_minutes": round(period.avg_session_minutes),
                "most_productive_weekday": period.most_productive_weekday,
                "least_productive_weekday": period.least_productive_weekday,
                "current_streak_days": period.current_streak,
                "scored_days": scored_days,
            },
            "category_minutes": dict(sorted(period.minutes_by_category.items())),
            "daily_reflections": [
                {"date": reflection.log_date, "note": reflection.notes[:800]}
                for reflection in reflections
            ],
            "daily": daily,
        }
