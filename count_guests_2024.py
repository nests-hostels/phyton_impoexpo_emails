"""
count_guests_2024.py

Count distinct users (by email) in the database that were in the hostels during a given year
(defaults to 2024). The script treats a record as a stay overlapping the year when the
checkin/checkout date ranges overlap the year window. It can print totals and per-hostel
breakdowns.

Assumptions:
- The database table (configured in emails_list_expbrevo.CONFIG) contains at least the
  columns: `email`, `checkin`, `checkout`, and `hostel` (hostel may be NULL/empty).
- Date columns are stored as DATE or DATETIME in MySQL; the query uses COALESCE to
  handle NULLs.

Usage:
    python count_guests_2024.py            # summary total for 2024
    python count_guests_2024.py --year 2023 --per-hostel

Notes:
- This script imports the existing `emails_list_expbrevo` module to reuse the
  `connect_to_database()` function and `CONFIG` table name.
"""

from __future__ import annotations
import argparse
import logging
import sys
from typing import Dict, Any

# Import connection helper and CONFIG from the existing module
from emails_list_expbrevo import connect_to_database, CONFIG


def count_distinct_guests(conn, year: int = 2024, per_hostel: bool = False) -> Dict[str, Any]:
    """Count distinct emails overlapping the given year.

    Returns a dict with 'total' and optionally 'per_hostel' mapping.
    Overlap condition (range intersection): NOT (checkout < year_start OR checkin > year_end)
    Uses COALESCE to handle NULL checkin/checkout.
    """
    cursor = conn.cursor(dictionary=True)
    table = CONFIG['DATABASE']['table']

    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"

    # Base WHERE: non-empty email
    # Also with empty base_where = "email IS NOT NULL AND TRIM(email) <> ''"

    # Overlap condition using COALESCE for NULLs
    overlap = (
        "NOT (COALESCE(checkout, '9999-12-31') < %s OR COALESCE(checkin, '0001-01-01') > %s)"
    )

    result: Dict[str, Any] = {'total': 0}

    try:
        if per_hostel:
            sql = (
                f"SELECT hostel, COUNT(DISTINCT email) AS cnt"
                f" FROM {table}"
                f" WHERE {overlap}"
                f" GROUP BY hostel ORDER BY cnt DESC"
            )
            # removed from WHERE {base_where} AND

            cursor.execute(sql, (year_start, year_end))
            rows = cursor.fetchall()
            per_hostel = {row.get('hostel') or 'UNKNOWN': row['cnt'] for row in rows}
            # Also get total distinct (in case some emails have NULL hostel)
            sql_total = (
                f"SELECT COUNT(DISTINCT email) AS total"
                f" FROM {table}"
                f" WHERE {overlap}"
            )
            # removed from WHERE {base_where} AND

            cursor.execute(sql_total, (year_start, year_end))
            total_row = cursor.fetchone()
            result['total'] = total_row['total'] if total_row else 0
            result['per_hostel'] = per_hostel
        else:
            sql = (
                f"SELECT COUNT(DISTINCT email) AS total"
                f" FROM {table}"
                f" WHERE {overlap}"
            )
            # remove from WHERE {base_where} AND
            cursor.execute(sql, (year_start, year_end))
            row = cursor.fetchone()
            result['total'] = row['total'] if row else 0

    except Exception as e:
        logging.error("Error counting guests: %s", e)
        raise
    finally:
        cursor.close()

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Count distinct users who stayed during a year')
    parser.add_argument('--year', type=int, default=2024, help='Year to analyze (default: 2024)')
    parser.add_argument('--per-hostel', action='store_true', help='Show breakdown per hostel')
    args = parser.parse_args(argv)

    # Connect to DB using helper from emails_list_expbrevo
    conn = connect_to_database()
    if not conn:
        logging.error('Could not connect to database. Check configuration in emails_list_expbrevo.CONFIG')
        sys.exit(2)

    try:
        stats = count_distinct_guests(conn, year=args.year, per_hostel=args.per_hostel)

        print('\n' + '=' * 60)
        print(f"Guest count overlapping year {args.year}")
        print('-' * 60)
        print(f"Total distinct emails: {stats.get('total', 0)}")

        if args.per_hostel:
            print('\nPer-hostel breakdown:')
            per = stats.get('per_hostel', {})
            for hostel, cnt in sorted(per.items(), key=lambda x: x[1], reverse=True):
                print(f"  {hostel}: {cnt}")

        print('=' * 60 + '\n')

    finally:
        conn.close()


if __name__ == '__main__':
    main()
