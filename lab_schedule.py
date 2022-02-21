import datetime
import os.path
import pickle
import time

import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def build_calendar_api():
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("calendar", "v3", credentials=creds)

    return service


def change_event_time_to_jst(events, mode="start"):
    events_starttime = []
    for event in events:
        if "date" in event[mode].keys():
            events_starttime.append(event[mode]["date"])
        else:
            str_event_uct_time = event[mode]["dateTime"]
            event_jst_time = datetime.datetime.strptime(
                str_event_uct_time, "%Y-%m-%dT%H:%M:%S+09:00"
            )
            str_event_jst_time = event_jst_time.strftime("%Y-%m-%dT%H:%M:%S")
            events_starttime.append(str_event_jst_time)
    return events_starttime


def search_events(service, calendar_id, start, num_month):

    end_datetime = datetime.datetime.strptime(start, "%Y-%m-%d") + relativedelta(
        months=num_month
    )
    end = end_datetime.strftime("%Y-%m-%d")

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start + "T00:00:00+09:00",  # NOTE:+09:00とするのが肝。（UTCをJSTへ変換）
            timeMax=end + "T23:59:00+09:00",  # NOTE;来月までをサーチ期間に。
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        return None, None, None, None
    else:
        events_starttime = change_event_time_to_jst(events, "start")
        events_endtime = change_event_time_to_jst(events, "end")
        return (
            [
                event["summary"] + "-" + event_starttime
                for event, event_starttime in zip(events, events_starttime)
            ],
            [event["summary"] for event in events],
            events_starttime,
            events_endtime,
        )


def filtering_event(event_name):
    """
    該当
    - 「土井」が含まれている
    - 他の人の名前が含まれていない（「進捗報告」は除く）

    Args:
        event_name ([type]): [description]

    Returns:
        [type]: [description]
    """

    # 他の人のイベントの特定
    other_names = ["野村", "鳥内", "土野", "宮迫", "野澤", "山内", "早川", "横手"]
    has_other_name = any(
        [True if other_name in event_name else False for other_name in other_names]
    )

    if "土井" in event_name or "進捗報告" in event_name:
        is_filtering = True
    elif has_other_name:
        is_filtering = False  # NOTE;「土井」が含まれているかどうかは、すでに判定しているので、ここでは「土井」が含まれていなくて、他のメンバーが含まれているeventが対象に
    else:
        is_filtering = True  # NOTE:誰の名前も含まれていないeventは全て対象

    return is_filtering


def filtering_events(events_name, events_starttime, events_endtime):

    my_events = [
        (event_name, event_starttime, event_endtime)
        for event_name, event_starttime, event_endtime in zip(
            events_name, events_starttime, events_endtime
        )
        if filtering_event(event_name)
    ]
    my_events_name = [my_event[0] for my_event in my_events]
    my_events_starttime = [my_event[1] for my_event in my_events]
    my_events_endtime = [my_event[2] for my_event in my_events]

    return my_events_name, my_events_starttime, my_events_endtime


def search_is_date(event_starttime):
    if ":" in event_starttime:
        is_date = False
    else:
        is_date = True
    return is_date


def add_info_to_calendar(calendarId, summary, start, end, is_date):

    if is_date:
        event = {
            "summary": summary,
            "start": {
                "date": start,
                "timeZone": "Japan",
            },
            "end": {
                "date": end,
                "timeZone": "Japan",
            },
        }
    else:
        event = {
            "summary": summary,
            "start": {"dateTime": start, "timeZone": "Japan"},
            "end": {
                "dateTime": end,
                "timeZone": "Japan",
            },
        }

    event = (
        service.events()
        .insert(
            calendarId=calendarId,
            body=event,
        )
        .execute()
    )


if __name__ == "__main__":
    original_calendar_id = "tv5hddhbuldi5610atsoqanvvk@group.calendar.google.com"
    my_calendar_id = "efhhfki4jgpvq2q8eq4fv2nq78@group.calendar.google.com"
    service = build_calendar_api()
    start = datetime.datetime.today().strftime("%Y-%m-%d")
    num_month = 3  # NOTE:3ヶ月先までを対象に

    (
        _,
        original_events_name,
        original_events_starttime,
        original_events_endtime,
    ) = search_events(service, my_calendar_id, start, num_month)
    print(original_events_name)
    print(original_events_starttime)
    print(original_events_endtime)
    raise
    (previous_my_events_info, _, _, _) = search_events(
        service, my_calendar_id, start, num_month
    )

    my_events_name, my_events_starttime, my_events_endtime = filtering_events(
        original_events_name, original_events_starttime, original_events_endtime
    )

    for my_event_name, my_event_starttime, my_event_endtime in zip(
        my_events_name, my_events_starttime, my_events_endtime
    ):

        if (
            f"{my_event_name}-{my_event_starttime}" in previous_my_events_info
        ):  # NOTE:同じ予定がすでに存在する場合はパス
            pass
        else:
            is_date = search_is_date(my_event_starttime)
            add_info_to_calendar(
                my_calendar_id,
                my_event_name,
                my_event_starttime,
                my_event_endtime,
                is_date,
            )
