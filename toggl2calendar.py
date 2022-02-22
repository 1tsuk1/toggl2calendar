import os
from pathlib import Path

import pickle


import requests
from requests.auth import HTTPBasicAuth

import datetime
from dateutil.relativedelta import relativedelta


from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


TOGGL_API_TOKEN = os.environ["TOGGL_API_TOKEN"]
LOG_GOOGLE_CALENDAR_ID = os.environ["LOG_GOOGLE_CALENDAR_ID"]

SECRET_DIR = "secret"
SECRET_DIR_PATH = Path(SECRET_DIR)
CREDENTIALS_NAME = "credentials.json"
TOKEN_NAME = "token.pickle"


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


def convert_date_jst(start):
    tdatetime = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S+00:00")
    # event_jst_time = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S+09:00")
    event_jst_time = tdatetime + datetime.timedelta(hours=9)
    str_event_jst_time = event_jst_time.strftime("%Y-%m-%dT%H:%M:%S")

    return str_event_jst_time


class TogglClient():

    @staticmethod
    def get_reports():
        """
            togglの作業ログをjsonで取得する関数
        """
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
            auth=auth,
            headers=headers,
            params=params,
        )
        json_r = r.json()

        return json_r


class GoogleCalendarClient():

    def __init__(self,google_calendar_ID):
        self.google_calendar_ID = google_calendar_ID
        self.google_api = ["https://www.googleapis.com/auth/calendar"]
        self.service = self._build_calendar_api()


    def _build_calendar_api(self):

        creds = None
        token_path = SECRET_DIR_PATH / TOKEN_NAME
        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(SECRET_DIR_PATH / CREDENTIALS_NAME, self.google_api)
                creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        service = build("calendar", "v3", credentials=creds)

        return service

    
    def search_events(self, end, num_month):

        start_datetime = datetime.datetime.strptime(end, "%Y-%m-%d") - relativedelta(
            months=num_month
        )
        start = start_datetime.strftime("%Y-%m-%d")

        events_result = (
            self.service.events()
            .list(
                calendarId=self.google_calendar_ID,
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
        
    def add_info_to_calendar(self, summary, start, end, is_date=False):

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
            self.service.events()
            .insert(
                calendarId=self.google_calendar_ID,
                body=event,
            )
            .execute()
        )




if __name__ == "__main__":

    google_calendar_client = GoogleCalendarClient(LOG_GOOGLE_CALENDAR_ID)

    end = datetime.datetime.today().strftime("%Y-%m-%d")
    num_month = 1
    results_for_calendar = []

    # 以前に書き込みを行った予定を取得
    (previous_my_events_info, _, _, _) = google_calendar_client.search_events(
        end, num_month
    )

    # TODO: togglから必要な情報を抜き出して、ここに渡す
    results = TogglClient.get_reports()
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
            google_calendar_client.add_info_to_calendar(
                my_event_name,
                my_event_starttime,
                my_event_endtime,
                is_date = False
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
