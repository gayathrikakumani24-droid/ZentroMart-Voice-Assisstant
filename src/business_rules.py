"""
Business date, holiday, and policy calculation rules for ZentroMart VoiceOps.

Reference Date: 20 October 2026 (Dataset fixed date).
Business Days: Monday to Saturday, excluding warehouse holidays in dataset/data/holidays.csv.
Return Windows: Counted in calendar days from delivery date.
Refund Timelines: Counted in business days from refund initiation date.
"""

from datetime import date, datetime, timedelta
from typing import Any, Optional, Dict, List, Tuple
from pathlib import Path
import csv
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "dataset" / "data"
HOLIDAYS_PATH = DATA_DIR / "holidays.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"

# Fixed dataset reference date (Tuesday, 20 October 2026)
REFERENCE_DATE = date(2026, 10, 20)
REFERENCE_DATE_STR = "2026-10-20"

_HOLIDAYS = None
_PRODUCTS = None


def parse_date(date_val):
    """Safely parse a date string (YYYY-MM-DD) or date object."""
    if date_val is None:
        return None
    if isinstance(date_val, date) and not isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    
    val_str = str(date_val).strip()
    if not val_str:
        return None
        
    # Match YYYY-MM-DD
    match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", val_str)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        
    # Match DD Month YYYY (e.g. 17 October 2026)
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    match2 = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", val_str)
    if match2:
        day = int(match2.group(1))
        m_str = match2.group(2).lower()
        year = int(match2.group(3))
        if m_str in months:
            return date(year, months[m_str], day)
            
    return None


def format_date_display(d: Any, lang: str = "en") -> str:
    """Format date for conversational display (e.g. '27 October 2026')."""
    if not d:
        return ""
    if isinstance(d, str):
        parsed = parse_date(d)
        if not parsed:
            return str(d)
        d = parsed
    months_en = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    months_hi = [
        "", "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
        "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"
    ]
    if lang.startswith("hi"):
        return f"{d.day} {months_hi[d.month]} {d.year}"
    return f"{d.day} {months_en[d.month]} {d.year}"


def get_holidays():
    """Load holidays from dataset/data/holidays.csv."""
    global _HOLIDAYS
    if _HOLIDAYS is not None:
        return _HOLIDAYS
        
    holidays = {}
    if HOLIDAYS_PATH.exists():
        with open(HOLIDAYS_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = parse_date(row["date"])
                if d:
                    holidays[d] = row.get("name", "Holiday")
    _HOLIDAYS = holidays
    return _HOLIDAYS


def is_business_day(d: date) -> bool:
    """
    Check if a date is a business day.
    Monday=0 ... Saturday=5 are business days.
    Sunday=6 is not a business day.
    Holidays in holidays.csv are excluded.
    """
    if d is None:
        return False
    if d.weekday() == 6:  # Sunday
        return False
    holidays = get_holidays()
    if d in holidays:
        return False
    return True


def add_business_days(start_date: date, num_days: int) -> date:
    """
    Add business days starting from start_date.
    The first business day counted is the first business day strictly after start_date.
    """
    if start_date is None or num_days <= 0:
        return start_date
        
    current = start_date
    added = 0
    while added < num_days:
        current += timedelta(days=1)
        if is_business_day(current):
            added += 1
    return current


def add_calendar_days(start_date: date, num_days: int) -> date:
    """Add calendar days to start_date."""
    if start_date is None:
        return None
    return start_date + timedelta(days=num_days)


def get_refund_timeline(payment_method: str):
    """
    Return (min_business_days, max_business_days, is_instant) for payment method [REF-2].
    """
    method = (payment_method or "").lower().strip()
    if "wallet" in method:
        return (0, 0, True)
    if "upi" in method:
        return (1, 3, False)
    if "card" in method or "credit" in method or "debit" in method:
        return (5, 7, False)
    if "netbanking" in method or "net_banking" in method or "net banking" in method:
        return (3, 5, False)
    if "cod" in method or "cash" in method or "neft" in method or "bank" in method:
        return (5, 7, False)
    # Default fallback to card timeline if unknown
    return (5, 7, False)


def calculate_refund_arrival(payment_method: str, initiated_date):
    """
    Calculate estimated arrival dates for refund based on payment method and initiation date.
    Returns dict with min_date, max_date, min_days, max_days, is_instant, and formatted strings.
    """
    init_d = parse_date(initiated_date)
    if not init_d:
        return None
        
    min_days, max_days, is_instant = get_refund_timeline(payment_method)
    if is_instant:
        return {
            "is_instant": True,
            "min_days": 0,
            "max_days": 0,
            "min_date": init_d,
            "max_date": init_d,
            "text_en": "Instant, within 2 hours",
            "text_hi": "तुरंत, 2 घंटे के भीतर",
        }
        
    min_date = add_business_days(init_d, min_days)
    max_date = add_business_days(init_d, max_days)
    
    return {
        "is_instant": False,
        "min_days": min_days,
        "max_days": max_days,
        "min_date": min_date,
        "max_date": max_date,
        "min_date_str": str(min_date),
        "max_date_str": str(max_date),
        "text_en": f"{min_days} to {max_days} business days ({format_date_display(min_date, 'en')} to {format_date_display(max_date, 'en')})",
        "text_hi": f"{min_days} से {max_days} कार्य दिवस ({format_date_display(min_date, 'hi')} से {format_date_display(max_date, 'hi')})",
    }


def get_return_window_days(category: str, delivery_date=None, order_date=None) -> int:
    """
    Get the return window in calendar days under ZentroMart policies.
    Enforces:
    - Festive sale [RET-8]: Clothing/footwear/bags ordered between 01 Oct 2026 and 15 Oct 2026 -> 30 days.
    - Electronics versioning [RET-3 & RETv3-2]:
      - Delivered before 01 Aug 2026: 10 days (v3).
      - Delivered on or after 01 Aug 2026: 7 days (v4).
    - Standard categories [RET-2]:
      - fashion (clothing, footwear, bags): 15 days
      - home_kitchen: 10 days
      - beauty_sealed: 7 days
      - books_media: 10 days
      - grocery, innerwear, digital: 0 days (not returnable)
    """
    cat = (category or "").lower().strip()
    deliv_d = parse_date(delivery_date)
    order_d = parse_date(order_date)
    
    # Festive sale check [RET-8]
    is_fashion = cat in ("fashion", "clothing", "footwear", "bags", "clothing, footwear and bags")
    if is_fashion and order_d:
        if date(2026, 10, 1) <= order_d <= date(2026, 10, 15):
            return 30

    # Electronics check [RET-3] vs [RETv3-2]
    if cat in ("electronics", "electronics and accessories"):
        if deliv_d and deliv_d < date(2026, 8, 1):
            return 10  # version 3 historical policy
        return 7       # version 4 current policy

    if is_fashion:
        return 15
    if cat in ("home_kitchen", "home, kitchen and furniture"):
        return 10
    if cat in ("beauty_sealed", "beauty and personal care", "beauty and personal care (unopened)"):
        return 7
    if cat in ("books_media", "books and stationery"):
        return 10
    if cat in ("grocery", "innerwear", "digital", "grocery, innerwear, gift cards"):
        return 0
        
    return 7  # default fallback


def calculate_return_deadline(delivery_date, category: str, order_date=None):
    """
    Calculate return deadline date from delivery date and category.
    Returns (deadline_date, window_days).
    """
    deliv_d = parse_date(delivery_date)
    if not deliv_d:
        return None, 0
    window = get_return_window_days(category, deliv_d, order_date)
    if window <= 0:
        return None, 0
    deadline = add_calendar_days(deliv_d, window)
    return deadline, window


def is_returnable_as_of(delivery_date, category: str, order_date=None, as_of_date=REFERENCE_DATE):
    """
    Check if an item is still within its return window as of as_of_date (default: 2026-10-20).
    """
    deadline, window = calculate_return_deadline(delivery_date, category, order_date)
    if not deadline:
        return False, None, window
    as_of = parse_date(as_of_date) or REFERENCE_DATE
    is_eligible = as_of <= deadline
    return is_eligible, deadline, window


def get_products():
    """Load products catalog from dataset/data/products.csv."""
    global _PRODUCTS
    if _PRODUCTS is not None:
        return _PRODUCTS
    products = {}
    if PRODUCTS_PATH.exists():
        with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                products[row["sku"]] = row
    _PRODUCTS = products
    return _PRODUCTS


def lookup_product(sku_or_title: str):
    """Lookup product by SKU or title substring."""
    if not sku_or_title:
        return None
    products = get_products()
    sku_clean = sku_or_title.strip().upper()
    if sku_clean in products:
        return products[sku_clean]
        
    # Search by SKU pattern inside string
    sku_match = re.search(r"\b([A-Z]{3}-\d{4})\b", sku_or_title, re.IGNORECASE)
    if sku_match:
        sku_found = sku_match.group(1).upper()
        if sku_found in products:
            return products[sku_found]
            
    # Substring match on title
    query_lower = sku_or_title.lower().strip()
    for prod in products.values():
        if prod["title"].lower() in query_lower or query_lower in prod["title"].lower():
            return prod
    return None
