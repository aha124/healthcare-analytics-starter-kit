"""Date utilities for healthcare analytics."""

from datetime import date, datetime, timedelta
from typing import Any

from config.logging_config import get_logger

logger = get_logger(__name__)


class DateUtils:
    """
    Date utility functions for healthcare analytics.

    Provides:
    - Date parsing from multiple formats
    - Date dimension key generation
    - Fiscal calendar support
    - Age calculation
    - Date range generation
    """

    # Common date formats to try when parsing
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%Y%m%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    # US Federal Holidays (dates that change each year need special handling)
    FIXED_HOLIDAYS = {
        (1, 1): "New Year's Day",
        (7, 4): "Independence Day",
        (11, 11): "Veterans Day",
        (12, 25): "Christmas Day",
    }

    @classmethod
    def parse_date(cls, value: Any, default: date | None = None) -> date | None:
        """
        Parse a date from various formats.

        Args:
            value: Date value to parse (string, date, datetime).
            default: Default value if parsing fails.

        Returns:
            Parsed date or default value.
        """
        if value is None:
            return default

        if isinstance(value, date) and not isinstance(value, datetime):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            value = value.strip()

            # Handle ISO format with timezone
            if "+" in value or value.endswith("Z"):
                value = value.split("+")[0].replace("Z", "")

            for fmt in cls.DATE_FORMATS:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue

        return default

    @classmethod
    def parse_datetime(
        cls,
        value: Any,
        default: datetime | None = None,
    ) -> datetime | None:
        """
        Parse a datetime from various formats.

        Args:
            value: Datetime value to parse.
            default: Default value if parsing fails.

        Returns:
            Parsed datetime or default value.
        """
        if value is None:
            return default

        if isinstance(value, datetime):
            return value

        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())

        if isinstance(value, str):
            value = value.strip()

            # Handle ISO format with timezone
            if "+" in value or value.endswith("Z"):
                value = value.split("+")[0].replace("Z", "")

            for fmt in cls.DATE_FORMATS:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        return default

    @staticmethod
    def get_date_key(dt: date | datetime | None) -> int | None:
        """
        Generate a date dimension key (YYYYMMDD format).

        Args:
            dt: Date or datetime to convert.

        Returns:
            Integer date key (e.g., 20240115) or None.
        """
        if dt is None:
            return None
        if isinstance(dt, datetime):
            dt = dt.date()
        return int(dt.strftime("%Y%m%d"))

    @staticmethod
    def from_date_key(date_key: int | str) -> date | None:
        """
        Convert a date key back to a date.

        Args:
            date_key: Integer or string in YYYYMMDD format.

        Returns:
            Date object or None.
        """
        try:
            key_str = str(date_key)
            return datetime.strptime(key_str, "%Y%m%d").date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def calculate_age(
        birth_date: date,
        as_of_date: date | None = None,
    ) -> int:
        """
        Calculate age in years.

        Args:
            birth_date: Date of birth.
            as_of_date: Date to calculate age as of (default: today).

        Returns:
            Age in years.
        """
        if as_of_date is None:
            as_of_date = date.today()

        age = as_of_date.year - birth_date.year

        # Adjust if birthday hasn't occurred yet this year
        if (as_of_date.month, as_of_date.day) < (birth_date.month, birth_date.day):
            age -= 1

        return max(0, age)

    @staticmethod
    def get_age_group(age: int) -> str:
        """
        Get age group category.

        Args:
            age: Age in years.

        Returns:
            Age group string.
        """
        if age < 0:
            return "unknown"
        if age < 1:
            return "infant"
        if age < 5:
            return "1-4"
        if age < 18:
            return "5-17"
        if age < 30:
            return "18-29"
        if age < 45:
            return "30-44"
        if age < 65:
            return "45-64"
        if age < 75:
            return "65-74"
        if age < 85:
            return "75-84"
        return "85+"

    @classmethod
    def get_fiscal_year(
        cls,
        dt: date,
        fiscal_year_start_month: int = 7,
    ) -> int:
        """
        Get fiscal year for a date.

        Args:
            dt: Date to check.
            fiscal_year_start_month: Month when fiscal year starts (1-12).

        Returns:
            Fiscal year number.
        """
        if dt.month >= fiscal_year_start_month:
            return dt.year + 1
        return dt.year

    @classmethod
    def get_fiscal_quarter(
        cls,
        dt: date,
        fiscal_year_start_month: int = 7,
    ) -> int:
        """
        Get fiscal quarter (1-4) for a date.

        Args:
            dt: Date to check.
            fiscal_year_start_month: Month when fiscal year starts.

        Returns:
            Fiscal quarter (1-4).
        """
        # Calculate months from fiscal year start
        months_from_start = (dt.month - fiscal_year_start_month) % 12
        return (months_from_start // 3) + 1

    @classmethod
    def is_holiday(cls, dt: date) -> tuple[bool, str | None]:
        """
        Check if a date is a US federal holiday.

        Args:
            dt: Date to check.

        Returns:
            Tuple of (is_holiday, holiday_name).
        """
        # Check fixed holidays
        if (dt.month, dt.day) in cls.FIXED_HOLIDAYS:
            return True, cls.FIXED_HOLIDAYS[(dt.month, dt.day)]

        # MLK Day: Third Monday in January
        if dt.month == 1 and dt.weekday() == 0:
            if 15 <= dt.day <= 21:
                return True, "Martin Luther King Jr. Day"

        # Presidents Day: Third Monday in February
        if dt.month == 2 and dt.weekday() == 0:
            if 15 <= dt.day <= 21:
                return True, "Presidents Day"

        # Memorial Day: Last Monday in May
        if dt.month == 5 and dt.weekday() == 0:
            if dt.day > 24:
                return True, "Memorial Day"

        # Labor Day: First Monday in September
        if dt.month == 9 and dt.weekday() == 0:
            if dt.day <= 7:
                return True, "Labor Day"

        # Columbus Day: Second Monday in October
        if dt.month == 10 and dt.weekday() == 0:
            if 8 <= dt.day <= 14:
                return True, "Columbus Day"

        # Thanksgiving: Fourth Thursday in November
        if dt.month == 11 and dt.weekday() == 3:
            if 22 <= dt.day <= 28:
                return True, "Thanksgiving Day"

        return False, None

    @classmethod
    def generate_date_range(
        cls,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """
        Generate a list of dates between start and end (inclusive).

        Args:
            start_date: Start of range.
            end_date: End of range.

        Returns:
            List of dates.
        """
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates

    @classmethod
    def build_date_dimension_record(cls, dt: date) -> dict[str, Any]:
        """
        Build a complete date dimension record.

        Args:
            dt: Date to build record for.

        Returns:
            Dictionary with all date dimension attributes.
        """
        is_holiday, holiday_name = cls.is_holiday(dt)
        today = date.today()

        return {
            "date_key": cls.get_date_key(dt),
            "full_date": dt,
            "year": dt.year,
            "quarter": (dt.month - 1) // 3 + 1,
            "month": dt.month,
            "month_name": dt.strftime("%B"),
            "week_of_year": dt.isocalendar()[1],
            "day_of_month": dt.day,
            "day_of_week": dt.weekday(),  # Monday = 0
            "day_name": dt.strftime("%A"),
            "day_of_year": dt.timetuple().tm_yday,
            "fiscal_year": cls.get_fiscal_year(dt),
            "fiscal_quarter": cls.get_fiscal_quarter(dt),
            "fiscal_month": ((dt.month - 7) % 12) + 1,
            "is_weekend": dt.weekday() >= 5,
            "is_holiday": is_holiday,
            "holiday_name": holiday_name,
            "is_current_day": dt == today,
            "is_current_week": dt.isocalendar()[1] == today.isocalendar()[1] and dt.year == today.year,
            "is_current_month": dt.month == today.month and dt.year == today.year,
            "is_current_year": dt.year == today.year,
        }


# Convenience functions


def parse_date(value: Any, default: date | None = None) -> date | None:
    """Parse a date value."""
    return DateUtils.parse_date(value, default)


def get_date_key(dt: date | datetime | None) -> int | None:
    """Get date dimension key."""
    return DateUtils.get_date_key(dt)


def calculate_age(birth_date: date, as_of_date: date | None = None) -> int:
    """Calculate age in years."""
    return DateUtils.calculate_age(birth_date, as_of_date)


def generate_date_dimension(
    start_year: int = 2020,
    end_year: int | None = None,
) -> list[dict[str, Any]]:
    """
    Generate date dimension records for a range of years.

    Args:
        start_year: First year to include.
        end_year: Last year to include (default: current year + 2).

    Returns:
        List of date dimension records.
    """
    if end_year is None:
        end_year = date.today().year + 2

    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)

    return [
        DateUtils.build_date_dimension_record(dt)
        for dt in DateUtils.generate_date_range(start_date, end_date)
    ]
