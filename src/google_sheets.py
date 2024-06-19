import functools
import logging
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file credentials.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = "1nieV8UzxUKOvO41vIu8YoceHL1_WbdVzoO_0ILliZpk"
DATA_RANGE = "dashboard!A3:Z3"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Record:
    def __init__(self, md5=None, sources=None, original_names=None, is_tatar=None):
        self.md5 = md5
        self.sources = sources
        self.original_names = original_names
        self.is_tatar = is_tatar

    @staticmethod
    def from_row(row: []):
        md5 = row[0] if len(row) > 0 else None
        sources = row[1].split(';') if len(row) > 1 else None
        original_names = row[2].split(';') if len(row) > 2 else None
        is_tatar = row[3] if len(row) > 3 else None
        return Record(md5, sources, original_names, is_tatar)

    def set_md5(self, md5: str):
        self.md5 = md5
        return self

    def set_source(self, sources: str):
        self.sources = sources
        return self

    def append_source(self, source: str):
        if self.sources is None:
            self.sources = []
        self.sources.append(source)
        return self

    def set_original_name(self, original_names: str):
        self.original_names = original_names
        return self

    def append_original_name(self, original_name: str):
        if self.original_names is None:
            self.original_names = []
        self.original_names.append(original_name)
        return self

    def set_tatar(self, is_tatar: bool):
        self.is_tatar = is_tatar
        return self

    def __str__(self):
        return f"Record(md5={self.md5}, sources={self.sources}, original_names={self.original_names}, is_tatar={self.is_tatar})"

    def is_empty(self):
        return self.md5 is None and self.sources is None and self.original_names is None and self.is_tatar is None

    def to_row(self):
        return [
            self.md5,
            ";".join(self.sources) if self.sources is not None else None,
            ";".join(self.original_names) if self.original_names is not None else None,
            self.is_tatar
        ]

    def merge(self, other):
        def func(a, b, mutator):
            if a is None and b is None:
                return None
            if a is not None and b is not None:
                return mutator(a, b)
            if a is None and b is not None:
                return b
            if a is not None and b is None:
                return a

        return Record(
            md5=func(self.md5, other.md5, lambda a, b: a),
            sources=func(self.sources, other.sources, lambda a, b: sorted(set(a + b))),
            original_names=func(self.original_names, other.original_names, lambda a, b: sorted(set(a + b))),
            is_tatar=func(self.is_tatar, other.is_tatar, lambda a, b: a or b)
        )


def _credentials():
    # todo find better way to get credentials
    creds = None
    if os.path.exists("token.json"):
        Credentials.from_
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds


@functools.cache
def _get_service():
    logger.error("Initializing Google Sheets service...")
    return build("sheets", "v4", credentials=_credentials())


def batch_get(ranges=["dashboard"]):
    return (
        _get_service()
        .spreadsheets()
        .values()
        .batchGet(spreadsheetId=SPREADSHEET_ID, ranges=ranges)
        .execute()
    )


def batch_update(rows, value_input_option="RAW"):
    data = list(map(lambda x: {'range': x[0], 'values': x[1]}, rows))
    (
        _get_service()
        .spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "valueInputOption": value_input_option,
                'data': data,
            },
        )
        .execute()
    )


def append(record: Record, range=DATA_RANGE, value_input_option="RAW"):
    if record.is_empty():
        return
    (
        _get_service()
        .spreadsheets()
        .values()
        .append(
            spreadsheetId=SPREADSHEET_ID,
            range=range,
            valueInputOption=value_input_option,
            body={"values": [record.to_row()]},
        )
        .execute()
    )


def update(range, record: Record, value_input_option="RAW"):
    if record.is_empty():
        return
    (
        _get_service()
        .spreadsheets()
        .values()
        .update(
            spreadsheetId=SPREADSHEET_ID,
            range=range,
            valueInputOption=value_input_option,
            body={"values": [record.to_row()]},
        )
        .execute()
    )


def get(range):
    return (
        _get_service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=range)
        .execute()
    )


def get_by_md5(md5: str):
    result = (
        _get_service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range="dashboard!A1:A9999")
        .execute()
    )
    row_number = 0
    found = False
    for row in result['values']:
        row_number += 1
        if len(row) > 0 and row[0] == md5:
            found = True
            break
    if not found:
        return None, None

    # todo smth wrong with numbers here
    rng = f"A{row_number}:Z{row_number}"

    print(f"Getting row with md5 {md5} from range {rng}")
    row = get(rng)
    if 'values' in row:
        row = row['values'][0]
    else:
        raise Exception(f"Row with md5 {md5} not found")
    return row, rng
