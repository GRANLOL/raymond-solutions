from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html import escape
from os import getenv

import database
import keyboards
import pandas as pd
from aiogram import F, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from analytics_service import build_stats_report as build_analytics_report
from booking_service import (
    cancel_booking_and_notify,
    finalize_web_booking,
    format_booking_history_text,
    format_user_booking_text,
)
from booking_validation import validate_web_booking as service_validate_web_booking
from category_service import build_category_list_text, filter_valid_parent_categories
from config import salon_config, update_config


async def get_user_roles(user_id: int) -> tuple[bool, bool]:
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(user_id) == admin_id)
    return is_admin, False


def is_admin(user_id: int) -> bool:
    admin_id = getenv("ADMIN_ID")
    return bool(admin_id and str(user_id) == admin_id)
