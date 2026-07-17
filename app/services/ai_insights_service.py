"""Prepare bounded local reports for the optional AI Coach."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from app.database.repositories.entry_repo import EntryRepository
from app.services.dashboard_service import DashboardService
from app.services.daily_progress_service import DailyProgressService
from app.services.daily_reflection_service import DailyReflectionService
from app.services.stats_service import StatsService
from app.utils import time_utils


class AiInsightsService:
    """Build JSON-ready tracker facts without contacting an AI provider."""

    RECENT_ACTIVE_DAYS = 60
    RECENT_MONTHS = 36
    TOP_CATEGORIES = 15
    RECENT_REFLECTIONS = 60
    MAX_REFLECTION_CHARS = 500

    def __init__(
        self,
        dashboard: DashboardService,
        progress: DailyProgressService,
        reflections: DailyReflectionService,
        stats: StatsService,
        entries: EntryRepository,
    ) -> None:
        self.dashboard = dashboard
        self.progress = progress
        self.reflections = reflections
        self.stats = stats
        self.entries = entries

    def all_history_report(self) -> dict[str, Any]:
        """Summarize the complete local database into a bounded AI packet.

        SQLite groups sessions before Python sees them. The report retains
        all-time/yearly totals while limiting detailed daily/monthly rows, so
        years of tracking do not make the Gemini request grow without bound.
        """
        daily_history = self.entries.daily_time_aggregates()
        category_history = self.entries.category_time_aggregates()
        recent_reflections = self.reflections.list_recent(self.RECENT_REFLECTIONS)

        monthly: dict[str, dict[str, int]] = defaultdict(
            lambda: {"productive_minutes": 0, "recorded_minutes": 0, "sessions": 0}
        )
        yearly: dict[str, dict[str, int]] = defaultdict(
            lambda: {"productive_minutes": 0, "recorded_minutes": 0, "sessions": 0}
        )
        weekdays: dict[int, dict[str, int]] = defaultdict(
            lambda: {
                "active_days": 0,
                "productive_minutes": 0,
                "recorded_minutes": 0,
            }
        )
        total_productive = 0
        total_recorded = 0
        total_sessions = 0

        for item in daily_history:
            log_date = str(item["date"])
            productive = int(item["productive_minutes"] or 0)
            recorded = int(item["recorded_minutes"] or 0)
            sessions = int(item["sessions"] or 0)
            total_productive += productive
            total_recorded += recorded
            total_sessions += sessions

            for bucket in (monthly[log_date[:7]], yearly[log_date[:4]]):
                bucket["productive_minutes"] += productive
                bucket["recorded_minutes"] += recorded
                bucket["sessions"] += sessions

            weekday = date.fromisoformat(log_date).weekday()
            weekdays[weekday]["active_days"] += 1
            weekdays[weekday]["productive_minutes"] += productive
            weekdays[weekday]["recorded_minutes"] += recorded

        weekday_names = (
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
        )
        weekday_patterns = []
        for weekday in range(7):
            values = weekdays.get(weekday)
            if not values:
                continue
            active_days = values["active_days"]
            weekday_patterns.append(
                {
                    "weekday": weekday_names[weekday],
                    "active_days": active_days,
                    "average_productive_minutes_on_active_days": round(
                        values["productive_minutes"] / active_days
                    ),
                    "average_recorded_minutes_on_active_days": round(
                        values["recorded_minutes"] / active_days
                    ),
                }
            )

        return {
            "source": "local_database_all_history",
            "privacy": (
                "Raw sessions stayed on device; only bounded aggregates and the latest "
                "saved daily reflections are included."
            ),
            "data_coverage": {
                "first_date": daily_history[0]["date"] if daily_history else None,
                "last_date": daily_history[-1]["date"] if daily_history else None,
                "active_days": len(daily_history),
                "sessions": total_sessions,
                "recent_reflections_included": len(recent_reflections),
                "reflection_limit": self.RECENT_REFLECTIONS,
            },
            "all_time_summary": {
                "productive_minutes": total_productive,
                "recorded_minutes": total_recorded,
                "active_days": len(daily_history),
                "categories": len(category_history),
            },
            "recent_daily": daily_history[-self.RECENT_ACTIVE_DAYS :],
            "recent_monthly": [
                {"month": month, **values}
                for month, values in sorted(monthly.items())[-self.RECENT_MONTHS :]
            ],
            "yearly_history": [
                {"year": year, **values} for year, values in sorted(yearly.items())
            ],
            "weekday_patterns": weekday_patterns,
            "top_categories": category_history[: self.TOP_CATEGORIES],
            "daily_reflections": [
                {
                    "date": reflection.log_date,
                    "note": reflection.notes[: self.MAX_REFLECTION_CHARS],
                }
                for reflection in recent_reflections
            ],
        }

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
