from fastapi import FastAPI, Query, HTTPException
import psycopg2
from typing import List, Dict
from datetime import time
from config import CONFIG
from constants import FETCH_WEEKLY_AVAILABILITY, FETCH_BLOCKED_AVAILABILITY
import logging

logging.basicConfig(level=logging.INFO)
app = FastAPI()


def get_db_connection():
    """Establish a database connection."""
    try:
        conn = psycopg2.connect(**CONFIG["database"])
        return conn
    except Exception as e:
        logging.error("Failed to connect to the database.")
        raise HTTPException(status_code=500, detail="Database connection error.")


def fetch_availability(cursor, user_ids: List[int]):
    """Fetch weekly availability for the given user IDs."""
    cursor.execute(FETCH_WEEKLY_AVAILABILITY, (user_ids,))
    availability = cursor.fetchall()
    if not availability:
        logging.warning("No users found in weekly availability for the provided user IDs.")
        raise HTTPException(status_code=404, detail="No users found in weekly availability for the provided user IDs.")
    return availability


def fetch_blocked_availability(cursor, user_ids: List[int]):
    """Fetch weekly blocked availability for the given user IDs."""
    cursor.execute(FETCH_BLOCKED_AVAILABILITY, (user_ids,))
    return cursor.fetchall()


def organize_availability(availability):
    """Organize availability data by user and date."""
    availability_map = {}
    for user_id, date, start_time, end_time in availability:
        key = (user_id, date)
        if key not in availability_map:
            availability_map[key] = []
        availability_map[key].append((start_time, end_time))
    return availability_map


def calculate_free_time(availability_map, blocked_map):
    """Calculate free time for each user by date."""
    user_free_time = {}
    for (user_id, date), avail_times in availability_map.items():
        blocked_times = blocked_map.get((user_id, date), [])
        blocked_times.sort()
        free_times = []

        for start_time, end_time in avail_times:
            current_start = start_time
            for blocked_start, blocked_end in blocked_times:
                if current_start < blocked_start:
                    free_times.append((current_start, blocked_start))
                current_start = max(current_start, blocked_end)
            if current_start < end_time:
                free_times.append((current_start, end_time))

        if date not in user_free_time:
            user_free_time[date] = []
        user_free_time[date].append(free_times)
    return user_free_time


def find_common_free_time(user_free_time, user_ids):
    """Find common free time for all users by date."""
    common_free_time = {}
    for date, free_time_lists in user_free_time.items():
        if len(free_time_lists) < len(user_ids):
            continue  # Skip dates where not all users have availability

        # Find intersection of free time ranges
        common_times = free_time_lists[0]
        for free_times in free_time_lists[1:]:
            temp_common = []
            for start1, end1 in common_times:
                for start2, end2 in free_times:
                    common_start = max(start1, start2)
                    common_end = min(end1, end2)
                    if common_start < common_end:
                        temp_common.append((common_start, common_end))
            common_times = temp_common

        # Format the result
        formatted_times = []
        for start, end in common_times:
            if isinstance(start, time) and isinstance(end, time):
                formatted_start = start.strftime("%I:%M%p").lower()
                formatted_end = end.strftime("%I:%M%p").lower()
                formatted_times.append(f"{formatted_start}-{formatted_end}")

        common_free_time[date.strftime("%d-%m-%Y")] = formatted_times
    return common_free_time


def fetch_common_free_time(user_ids: List[int]) -> Dict[str, List[str]]:
    """Main function to fetch common free time."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        logging.info("Fetching weekly availability...")
        availability = fetch_availability(cursor, user_ids)

        logging.info("Fetching blocked availability...")
        blocked_availability = fetch_blocked_availability(cursor, user_ids)

        logging.info("Organizing availability data...")
        availability_map = organize_availability(availability)
        blocked_map = organize_availability(blocked_availability)

        logging.info("Calculating free time...")
        user_free_time = calculate_free_time(availability_map, blocked_map)

        logging.info("Finding common free time...")
        return find_common_free_time(user_free_time, user_ids)

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.get("/common_free_time", response_model=Dict[str, List[str]])
def get_common_free_time(user_ids: List[int] = Query(...)):
    return fetch_common_free_time(user_ids)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
