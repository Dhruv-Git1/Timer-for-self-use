"""Daily checkbox/counter actions and Android's unit-neutral Today score."""

from __future__ import annotations

from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.daily_progress_repo import DailyProgressRepository
from app.database.repositories.entry_repo import EntryRepository
from app.models.category import TRACKING_CHECKOFF, TRACKING_COUNTER
from app.models.daily_progress import DailyScore, DailyScoreItem
from app.services import aggregation
from app.utils import time_utils
from app.utils.event_bus import bus, DATA_CHANGED


class DailyProgressService:
    """Mutate non-timer progress and calculate the separate Android score."""

    def __init__(
        self,
        progress_repo: DailyProgressRepository,
        category_repo: CategoryRepository,
        entry_repo: EntryRepository,
    ) -> None:
        self.progress = progress_repo
        self.categories = category_repo
        self.entries = entry_repo

    def _category(self, category_id: int):
        category = self.categories.get(category_id)
        if category is None or category.is_archived:
            raise ValueError("Category is unavailable.")
        return category

    def get(self, category_id: int, log_date: str) -> int:
        category = self._category(category_id)
        if category.is_timer:
            raise ValueError("Timer progress is calculated from time entries.")
        return self.progress.get_value(category_id, log_date)

    def toggle(self, category_id: int, log_date: str) -> int:
        category = self._category(category_id)
        if category.tracking_mode != TRACKING_CHECKOFF:
            raise ValueError("Only Check-off categories can be toggled.")
        value = 0 if self.progress.get_value(category_id, log_date) else 1
        self.progress.set_value(category_id, log_date, value)
        bus.publish(DATA_CHANGED, date=log_date)
        return value

    def increment(self, category_id: int, log_date: str, delta: int) -> int:
        category = self._category(category_id)
        if category.tracking_mode != TRACKING_COUNTER:
            raise ValueError("Only Counter categories can be adjusted.")
        current = self.progress.get_value(category_id, log_date)
        value = self.progress.set_value(category_id, log_date, max(0, current + int(delta)))
        bus.publish(DATA_CHANGED, date=log_date)
        return value

    def set_amount(self, category_id: int, log_date: str, amount: int) -> int:
        category = self._category(category_id)
        if category.tracking_mode != TRACKING_COUNTER:
            raise ValueError("Only Counter categories can be set directly.")
        if int(amount) < 0:
            raise ValueError("Counter amount cannot be negative.")
        value = self.progress.set_value(category_id, log_date, int(amount))
        bus.publish(DATA_CHANGED, date=log_date)
        return value

    def score(self, log_date: str) -> DailyScore:
        categories = self.categories.list_all(include_archived=False)
        previous = time_utils.add_days(log_date, -1)
        entries = self.entries.list_by_date_range(previous, log_date)
        minutes = aggregation.build_day_category_minutes(entries, log_date, log_date).get(
            log_date, {}
        )

        items: list[DailyScoreItem] = []
        for category in categories:
            target = category.target_value
            if target <= 0:
                continue
            actual = (
                minutes.get(category.id, 0)
                if category.is_timer
                else self.progress.get_value(category.id, log_date)
            )
            items.append(
                DailyScoreItem(
                    category_id=category.id,
                    name=category.name,
                    color=category.color,
                    tracking_mode=category.tracking_mode,
                    actual=actual,
                    target=target,
                    unit_label=category.unit_label,
                    included=category.include_in_daily_score,
                    weight=category.score_weight,
                )
            )
        return DailyScore(date=log_date, items=items)
