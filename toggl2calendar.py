import datetime
import os.path
import pickle
import time
from dataclasses import field
from datetime import datetime as dt
from datetime import timedelta

import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests.auth import HTTPBasicAuth

TOGGL_API_TOKEN = "93e6fe8d540b1d00d20f87cad671eb0b"


def get_reports():
    headers = {"content-type": "application/json"}
    auth = HTTPBasicAuth(TOGGL_API_TOKEN, "api_token")
    params = {
        # "time_entry": {}
        # 'user_agent': EMAIL,
        # 'workspace_id': workspace_id,
        # "start": start,
        # "stop": "2022-03-11",
    }

    r = requests.get(
        "https://api.track.toggl.com/api/v8/time_entries",
        # 'https://track.toggl.com/api/v8/time_entries/',
        auth=auth,
        headers=headers,
        params=params,
    )
    print(r)
    json_r = r.json()

    return json_r


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


def search_events(service, calendar_id, end, num_month):

    start_datetime = datetime.datetime.strptime(end, "%Y-%m-%d") - relativedelta(
        months=num_month
    )
    start = start_datetime.strftime("%Y-%m-%d")

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


def add_info_to_calendar(calendarId, summary, start, end, is_date=False):

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


# def convert_tstr_2_datetime(tstr):
#     # tstr = '2012-12-29 13:49:37'
#     tdatetime = dt.strptime(tstr, "%Y-%m-%dT%H:%M:%S+00:00")
#     # tdatetime = dt.strptime(tstr, "%Y-%m-%dT00:%H:%M:%S+00:00")

#     return tdatetime


def convert_second_2_minutes(second):
    return round(second / 60)


def convert_date_jst(start):
    tdatetime = dt.strptime(start, "%Y-%m-%dT%H:%M:%S+00:00")
    # event_jst_time = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S+09:00")
    event_jst_time = tdatetime + datetime.timedelta(hours=9)
    str_event_jst_time = event_jst_time.strftime("%Y-%m-%dT%H:%M:%S")

    return str_event_jst_time


if __name__ == "__main__":
    my_calendar_id = "efhhfki4jgpvq2q8eq4fv2nq78@group.calendar.google.com"
    service = build_calendar_api()
    end = datetime.datetime.today().strftime("%Y-%m-%d")
    num_month = 1
    results_for_calendar = []

    # 以前に書き込みを行った予定を取得
    (previous_my_events_info, _, _, _) = search_events(
        service, my_calendar_id, end, num_month
    )

    # TODO: togglから必要な情報を抜き出して、ここに渡す
    results = get_reports()
    results = results[::-1]
    for i, result in enumerate(results):

        current_result_dict = {}

        try:

            # タイトル
            current_result_dict["title"] = result["description"]

            # 開始時間
            current_result_dict["start"] = result["start"]
            current_result_dict["end"] = result["stop"]

            results_for_calendar.append(current_result_dict)
        except:
            print("skip... ")

    # TODO:情報を渡す
    for result_for_calendar in results_for_calendar:
        my_event_name = result_for_calendar["title"]
        my_event_starttime = convert_date_jst(result_for_calendar["start"])
        my_event_endtime = convert_date_jst(result_for_calendar["end"])

        # print(previous_my_events_info)
        # print("━━━━━━━━━━")
        # print(my_event_name)
        # print(my_event_starttime)
        # print(my_event_endtime)
        if (
            f"{my_event_name}-{my_event_starttime}" in previous_my_events_info
        ):  # NOTE:同じ予定がすでに存在する場合はパス
            pass
        else:
            add_info_to_calendar(
                my_calendar_id,
                my_event_name,
                my_event_starttime,
                my_event_endtime,
            )

    # NOTE: テスト
    # my_event_name = "test"
    # my_event_starttime = "2022-02-22T00:00:00+09:00"
    # my_event_endtime = "2022-02-22T09:00:00+09:00"
    # add_info_to_calendar(
    #     my_calendar_id,
    #     my_event_name,
    #     my_event_starttime,
    #     my_event_endtime,
    # )
