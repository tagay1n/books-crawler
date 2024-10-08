# import functools
# import json
# import os.path
#
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
#
# # If modifying these scopes, delete the file credentials.json.
# SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
#
# # The ID and range of a sample spreadsheet.
# BOOKS_SPREADSHEET_ID = "1nieV8UzxUKOvO41vIu8YoceHL1_WbdVzoO_0ILliZpk"
# AUDIOBOOKS_SPREADSHEET_ID = "1nGYtZ8_vmN74qOPqqOfCcDvJT9Wj_unDU_X7nkklEN0"
# DATA_RANGE = "dashboard!A3:Z3"
#
#
# class Record:
#     def __init__(self, md5=None, sources=None, original_names=None, is_tatar=None, meta=None):
#         self.md5 = md5
#         self.sources = sources
#         self.original_names = original_names
#         self.is_tatar = is_tatar
#         self.meta = meta
#
#     @staticmethod
#     def from_row(row: []):
#         md5 = row[0] if len(row) > 0 else None
#         sources = set(row[1].split(';')) if len(row) > 1 else None
#         original_names = set(row[2].split(';')) if len(row) > 2 else None
#         is_tatar = row[3] if len(row) > 3 else None
#         return Record(md5, sources, original_names, is_tatar)
#
#     def set_md5(self, md5: str):
#         self.md5 = md5
#         return self
#
#     def set_source(self, sources: str):
#         self.sources = sources
#         return self
#
#     def append_source(self, source: str):
#         if self.sources is None:
#             self.sources = set()
#         self.sources.add(source)
#         return self
#
#     def set_original_name(self, original_names: str):
#         self.original_names = original_names
#         return self
#
#     def append_original_name(self, original_name: str):
#         if self.original_names is None:
#             self.original_names = set()
#         self.original_names.add(original_name)
#         return self
#
#     def set_tatar(self, is_tatar: bool):
#         self.is_tatar = is_tatar
#         return self
#
#     def set_meta(self, meta):
#         self.meta = meta
#         return self
#
#     def __str__(self):
#         return f"Record(md5={self.md5}, sources={self.sources}, original_names={self.original_names}, is_tatar={self.is_tatar})"
#
#     def is_empty(self):
#         return self.md5 is None and self.sources is None and self.original_names is None and self.is_tatar is None
#
#     def to_row(self):
#         return [
#             self.md5,
#             ";".join(self.sources) if self.sources is not None else None,
#             ";".join(self.original_names) if self.original_names is not None else None,
#             self.is_tatar,
#             json.dumps(self.meta, ensure_ascii=False, indent=4) if self.meta is not None else None
#         ]
#
#     def merge(self, other):
#         def func(a, b, mutator):
#             if a is None and b is None:
#                 return None
#             if a is not None and b is not None:
#                 return mutator(a, b)
#             if a is None and b is not None:
#                 return b
#             if a is not None and b is None:
#                 return a
#
#         return Record(
#             md5=func(self.md5, other.md5, lambda a, b: a),
#             sources=func(self.sources, other.sources, lambda a, b: sorted(a.union(b))),
#             original_names=func(self.original_names, other.original_names, lambda a, b: sorted(a.union(b))),
#             is_tatar=func(self.is_tatar, other.is_tatar, lambda a, b: a or b),
#             meta=self.meta
#         )
#
#
# def _credentials():
#     creds = None
#     if os.path.exists("../../token.json"):
#         creds = Credentials.from_authorized_user_file("../../token.json", SCOPES)
#     # If there are no (valid) credentials available, let the user log in.
#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file(
#                 "../../credentials.json", SCOPES
#             )
#             creds = flow.run_local_server(port=0)
#         # Save the credentials for the next run
#         with open("../../token.json", "w") as token:
#             token.write(creds.to_json())
#
#     return creds
#
#
# # just check credentials is ok
# # _credentials()
#
#
# @functools.cache
# def _get_service():
#     print("Initializing Google Sheets service...")
#     return build("sheets", "v4", credentials=_credentials())
#
#
# def batch_get(ranges=["dashboard"], spreadsheet_id=BOOKS_SPREADSHEET_ID):
#     return (
#         _get_service()
#         .spreadsheets()
#         .values()
#         .batchGet(spreadsheetId=spreadsheet_id, ranges=ranges)
#         .execute()
#     )
#
#
# def batch_update(rows, value_input_option="RAW", spreadsheet_id=BOOKS_SPREADSHEET_ID):
#     data = list(map(lambda x: {'range': x[0], 'values': x[1]}, rows))
#     (
#         _get_service()
#         .spreadsheets()
#         .values()
#         .batchUpdate(
#             spreadsheetId=spreadsheet_id,
#             body={
#                 "valueInputOption": value_input_option,
#                 'data': data,
#             },
#         )
#         .execute()
#     )
#
#
# def append(record: Record, range=DATA_RANGE, value_input_option="RAW", spreadsheet_id=BOOKS_SPREADSHEET_ID):
#     if record.is_empty():
#         return
#     (
#         _get_service()
#         .spreadsheets()
#         .values()
#         .append(
#             spreadsheetId=spreadsheet_id,
#             range=range,
#             valueInputOption=value_input_option,
#             body={"values": [record.to_row()]},
#         )
#         .execute()
#     )
#
#
# def update(rng, record: Record, value_input_option="RAW", spreadsheet_id=BOOKS_SPREADSHEET_ID):
#     if record.is_empty():
#         return
#     (
#         _get_service()
#         .spreadsheets()
#         .values()
#         .update(
#             spreadsheetId=spreadsheet_id,
#             range=rng,
#             valueInputOption=value_input_option,
#             body={"values": [record.to_row()]},
#         )
#         .execute()
#     )
#
#
# def get(range, spreadsheet_id=BOOKS_SPREADSHEET_ID):
#     return (
#         _get_service()
#         .spreadsheets()
#         .values()
#         .get(spreadsheetId=spreadsheet_id, range=range)
#         .execute()
#     )
#
#
# def get_by_md5(md5: str, spreadsheet_id=BOOKS_SPREADSHEET_ID):
#     result = (
#         _get_service()
#         .spreadsheets()
#         .values()
#         .get(spreadsheetId=spreadsheet_id, range="dashboard!A1:A9999")
#         .execute()
#     )
#     row_number = 0
#     found = False
#     for row in result['values']:
#         row_number += 1
#         if len(row) > 0 and row[0] == md5:
#             found = True
#             break
#     if not found:
#         return None, None
#
#     # todo smth wrong with numbers here
#     rng = f"A{row_number}:Z{row_number}"
#
#     print(f"Getting row with md5 {md5} from range {rng}")
#     row = get(rng)
#     if 'values' in row:
#         row = row['values'][0]
#     else:
#         raise Exception(f"Row with md5 {md5} not found")
#     return row, rng
