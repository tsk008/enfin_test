FETCH_WEEKLY_AVAILABILITY = """
    SELECT user_id, date, start_time, end_time
    FROM public.weekly_availability
    WHERE user_id = ANY(%s)
"""

FETCH_BLOCKED_AVAILABILITY = """
    SELECT user_id, date, start_time, end_time
    FROM public.weekly_blocked_availability
    WHERE user_id = ANY(%s)
"""