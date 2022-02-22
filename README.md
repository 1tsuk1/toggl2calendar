# toggl2calendar
togglのログをgoogle calendarに反映する

## 準備

- TOGGL_API_TOKENとLOG_GOOGLE_CALENDAR_IDを環境変数として設定
  - TOGGL_API_TOKEN: TogglのAPI
  - LOG_GOOGLE_CALENDAR_ID: 作業ログを反映するgoogle calendarのID
- secretディレクトリにcredentials.jsonとtoken.pickleを用意（googleAPIを利用するために使用）
- `pip install -r requirements.txt` でライブラリをinstall


## 実行コマンド

```
python toggl2calendar.py
```
