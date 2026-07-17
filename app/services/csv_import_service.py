"""Safe, preview-first import of Time Tracker CSV exports."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import config
from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository
from app.models.category import TRACKING_TIMER, Category
from app.utils import time_utils, validators
from app.utils.event_bus import DATA_CHANGED, bus

_REQUIRED_COLUMNS = {
    "date",
    "start_time",
    "end_time",
    "duration_minutes",
    "category",
    "productive",
    "notes",
}
_TRUE_VALUES = {"true", "1", "yes"}
_FALSE_VALUES = {"false", "0", "no"}
_MAX_ISSUES = 25


@dataclass(frozen=True)
class CsvImportIssue:
    row_number: int
    message: str


@dataclass(frozen=True)
class CsvCategoryConflict:
    category: str
    existing_productive: bool
    imported_productive: bool


@dataclass(frozen=True)
class _ImportRow:
    row_number: int
    category_name: str
    productive: bool
    log_date: str
    start_ts: str
    end_ts: str
    duration_minutes: int
    crosses_midnight: bool
    notes: str

    @property
    def duplicate_key(self) -> tuple[str, str, str]:
        return (self.category_name.casefold(), self.start_ts, self.end_ts)


@dataclass(frozen=True)
class CsvImportPreview:
    source_name: str
    file_hash: str
    total_rows: int
    valid_rows: int
    duplicate_rows: int
    new_category_names: tuple[str, ...]
    existing_category_conflicts: tuple[CsvCategoryConflict, ...]
    issues: tuple[CsvImportIssue, ...]
    import_allowed: bool
    _rows: tuple[_ImportRow, ...] = field(repr=False, compare=False)
    _source_path: Optional[str] = field(default=None, repr=False, compare=False)
    _source_bytes: Optional[bytes] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class CsvImportResult:
    imported_entries: int
    skipped_duplicates: int
    created_categories: int


class CsvImportService:
    """Parses a CSV fully before allowing one atomic database import."""

    def __init__(self, entry_repo: EntryRepository, category_repo: CategoryRepository) -> None:
        self.entries = entry_repo
        self.categories = category_repo

    def preview(
        self, source: str | Path | bytes, *, source_name: Optional[str] = None
    ) -> CsvImportPreview:
        """Validate a file or bytes without changing the database."""
        data, name, path = self._read_source(source, source_name)
        return self._build_preview(data, name, path)

    def import_preview(self, preview: CsvImportPreview) -> CsvImportResult:
        """Revalidate a preview and commit all new categories/entries together."""
        if preview._source_path:
            data = Path(preview._source_path).read_bytes()
        elif preview._source_bytes is not None:
            data = preview._source_bytes
        else:  # defensive; callers cannot normally construct this state
            raise ValueError("Import source is unavailable.")
        if hashlib.sha256(data).hexdigest() != preview.file_hash:
            raise ValueError("The CSV changed after preview. Preview it again before importing.")

        fresh = self._build_preview(data, preview.source_name, preview._source_path)
        if not fresh.import_allowed:
            if fresh.total_rows == 0 and not fresh.issues:
                raise ValueError("This CSV has no entries to import.")
            message = fresh.issues[0].message if fresh.issues else "CSV import is not allowed."
            raise ValueError(message)

        existing_categories = {
            category.name.casefold(): category
            for category in self.categories.list_all(include_archived=True)
        }
        initial_category_count = len(existing_categories)
        conn = self.entries.conn
        created = 0
        imported = 0
        try:
            conn.execute("BEGIN")
            for name in fresh.new_category_names:
                first_row = next(row for row in fresh._rows if row.category_name.casefold() == name.casefold())
                color = config.CHART_PALETTE[
                    (initial_category_count + created) % len(config.CHART_PALETTE)
                ]
                sort_order = initial_category_count + created
                category_id = self.categories.create(
                    name,
                    color,
                    first_row.productive,
                    0,
                    sort_order,
                    TRACKING_TIMER,
                    1,
                    "times",
                    True,
                    1,
                    commit=False,
                )
                category = self.categories.get(category_id)
                if category is None:
                    raise RuntimeError("Created import category could not be read.")
                existing_categories[name.casefold()] = category
                created += 1

            existing_keys = self._existing_entry_keys()
            for row in fresh._rows:
                if row.duplicate_key in existing_keys:
                    continue
                category = existing_categories[row.category_name.casefold()]
                self.entries.create(
                    category.id,
                    row.log_date,
                    row.start_ts,
                    row.end_ts,
                    row.duration_minutes,
                    row.crosses_midnight,
                    row.notes,
                    commit=False,
                )
                existing_keys.add(row.duplicate_key)
                imported += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        bus.publish(DATA_CHANGED)
        return CsvImportResult(
            imported_entries=imported,
            skipped_duplicates=fresh.duplicate_rows,
            created_categories=created,
        )

    def _read_source(
        self, source: str | Path | bytes, source_name: Optional[str]
    ) -> tuple[bytes, str, Optional[str]]:
        if isinstance(source, bytes):
            return source, source_name or "selected.csv", None
        path = Path(source)
        return path.read_bytes(), source_name or path.name, str(path)

    def _build_preview(
        self, data: bytes, name: str, source_path: Optional[str]
    ) -> CsvImportPreview:
        digest = hashlib.sha256(data).hexdigest()
        issues: list[CsvImportIssue] = []
        rows: list[_ImportRow] = []
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return self._preview_with_error(name, digest, "CSV must be UTF-8 encoded.", source_path, data)

        try:
            reader = csv.DictReader(io.StringIO(text))
            raw_headers = reader.fieldnames or []
        except csv.Error as exc:
            return self._preview_with_error(name, digest, f"CSV could not be read: {exc}", source_path, data)
        headers = {header.strip().casefold() for header in raw_headers if header}
        missing = sorted(_REQUIRED_COLUMNS - headers)
        if missing:
            return self._preview_with_error(
                name,
                digest,
                "CSV is missing required columns: " + ", ".join(missing) + ".",
                source_path,
                data,
            )

        total_rows = 0
        try:
            for row_number, raw in enumerate(reader, start=2):
                total_rows += 1
                normalized = {
                    (key or "").strip().casefold(): (value or "")
                    for key, value in raw.items()
                }
                parsed, error = self._parse_row(normalized, row_number)
                if error:
                    self._append_issue(issues, CsvImportIssue(row_number, error))
                elif parsed is not None:
                    rows.append(parsed)
        except csv.Error as exc:
            self._append_issue(issues, CsvImportIssue(0, f"CSV could not be read: {exc}"))

        categories = self.categories.list_all(include_archived=True)
        by_name = {category.name.casefold(): category for category in categories}
        new_names: list[str] = []
        new_flags: dict[str, bool] = {}
        conflicts: list[CsvCategoryConflict] = []
        conflict_keys: set[str] = set()
        for row in rows:
            identity = row.category_name.casefold()
            existing = by_name.get(identity)
            if existing is not None:
                if existing.is_productive != row.productive and identity not in conflict_keys:
                    conflicts.append(
                        CsvCategoryConflict(row.category_name, existing.is_productive, row.productive)
                    )
                    conflict_keys.add(identity)
                continue
            if identity not in new_flags:
                ok, message = validators.validate_category_name(row.category_name, set())
                if not ok:
                    self._append_issue(issues, CsvImportIssue(row.row_number, message))
                    continue
                new_flags[identity] = row.productive
                new_names.append(row.category_name)
            elif new_flags[identity] != row.productive:
                self._append_issue(
                    issues,
                    CsvImportIssue(
                        row.row_number,
                        f'New category "{row.category_name}" has conflicting productive values.',
                    ),
                )

        existing_keys = self._existing_entry_keys()
        seen_keys: set[tuple[str, str, str]] = set()
        duplicate_rows = 0
        for row in rows:
            if row.duplicate_key in existing_keys or row.duplicate_key in seen_keys:
                duplicate_rows += 1
            seen_keys.add(row.duplicate_key)

        return CsvImportPreview(
            source_name=name,
            file_hash=digest,
            total_rows=total_rows,
            valid_rows=len(rows),
            duplicate_rows=duplicate_rows,
            new_category_names=tuple(new_names),
            existing_category_conflicts=tuple(conflicts),
            issues=tuple(issues),
            import_allowed=bool(rows) and not issues,
            _rows=tuple(rows),
            _source_path=source_path,
            _source_bytes=None if source_path else data,
        )

    def _preview_with_error(
        self,
        name: str,
        digest: str,
        message: str,
        path: Optional[str],
        data: bytes,
    ) -> CsvImportPreview:
        return CsvImportPreview(
            source_name=name,
            file_hash=digest,
            total_rows=0,
            valid_rows=0,
            duplicate_rows=0,
            new_category_names=(),
            existing_category_conflicts=(),
            issues=(CsvImportIssue(0, message),),
            import_allowed=False,
            _rows=(),
            _source_path=path,
            _source_bytes=None if path else data,
        )

    @staticmethod
    def _append_issue(issues: list[CsvImportIssue], issue: CsvImportIssue) -> None:
        if len(issues) < _MAX_ISSUES:
            issues.append(issue)

    @staticmethod
    def _parse_row(row: dict[str, str], row_number: int) -> tuple[Optional[_ImportRow], Optional[str]]:
        log_date = row.get("date", "").strip()
        start_time = row.get("start_time", "").strip()
        end_time = row.get("end_time", "").strip()
        category = row.get("category", "").strip()
        productive_raw = row.get("productive", "").strip().casefold()
        duration_raw = row.get("duration_minutes", "").strip()
        if not time_utils.is_valid_date(log_date):
            return None, "Date must be a valid ISO date (YYYY-MM-DD)."
        if not time_utils.is_valid_time(start_time):
            return None, "Start time must be in HH:MM 24-hour format."
        if not time_utils.is_valid_time(end_time):
            return None, "End time must be in HH:MM 24-hour format."
        if not category:
            return None, "Category cannot be empty."
        if productive_raw in _TRUE_VALUES:
            productive = True
        elif productive_raw in _FALSE_VALUES:
            productive = False
        else:
            return None, "Productive must be true/false, 1/0, or yes/no."
        if not duration_raw.isdigit():
            return None, "Duration minutes must be a whole number."
        try:
            start_ts, end_ts, computed_duration, crosses = time_utils.build_timestamps(
                log_date, start_time, end_time
            )
        except ValueError as exc:
            return None, str(exc)
        if int(duration_raw) != computed_duration:
            return None, "Duration minutes does not match start and end times."
        return (
            _ImportRow(
                row_number=row_number,
                category_name=category,
                productive=productive,
                log_date=log_date,
                start_ts=start_ts,
                end_ts=end_ts,
                duration_minutes=computed_duration,
                crosses_midnight=crosses,
                notes=row.get("notes", "").strip(),
            ),
            None,
        )

    def _existing_entry_keys(self) -> set[tuple[str, str, str]]:
        return {
            ((entry.category_name or "").casefold(), entry.start_ts, entry.end_ts)
            for entry in self.entries.list_all()
        }
