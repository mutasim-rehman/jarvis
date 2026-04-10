from enum import Enum

class IntentType(str, Enum):
    GENERAL_CHAT = "GENERAL_CHAT"
    OPEN_APP = "OPEN_APP"
    CLOSE_APP = "CLOSE_APP"
    HANDLE_ASSIGNMENTS = "HANDLE_ASSIGNMENTS"
    CHECK_ASSIGNMENTS = "CHECK_ASSIGNMENTS"
    START_PROJECT = "START_PROJECT"
    CREATE_PROJECT = "CREATE_PROJECT"
    RESUME_PROJECT = "RESUME_PROJECT"
    STUDY_MODE = "STUDY_MODE"
    FOCUS_MODE = "FOCUS_MODE"
    SEARCH_WEB = "SEARCH_WEB"
    OPEN_WEBSITE = "OPEN_WEBSITE"
    PLAY_MUSIC = "PLAY_MUSIC"
    STOP_MUSIC = "STOP_MUSIC"
    SYSTEM_CONTROL = "SYSTEM_CONTROL"
    FILE_OPERATION = "FILE_OPERATION"
    UNKNOWN = "UNKNOWN"

WORKFLOWS = {
  "OPEN_APP": [
    {"action": "OPEN_APP", "target": None}
  ],
  "CLOSE_APP": [
    {"action": "CLOSE_APP", "target": None}
  ],
  "CHECK_ASSIGNMENTS": [
    {"action": "OPEN_APP", "target": "chrome"},
    {"action": "OPEN_URL", "target": "gcr"},
    {"action": "LOGIN", "target": "gcr"},
    {"action": "FETCH_PENDING_ASSIGNMENTS"}
  ],
  "HANDLE_ASSIGNMENTS": [
    {"action": "OPEN_APP", "target": "chrome"},
    {"action": "OPEN_URL", "target": "gcr"},
    {"action": "LOGIN", "target": "gcr"},
    {"action": "FETCH_PENDING_ASSIGNMENTS"},
    {"action": "DOWNLOAD_ASSIGNMENTS"},
    {"action": "CREATE_FOLDER", "target": "assignments/latest"},
    {"action": "OPEN_APP", "target": "cursor"}
  ],
  "START_PROJECT": [
    {"action": "OPEN_APP", "target": "spotify"},
    {"action": "PLAY_PLAYLIST", "target": "coding"},
    {"action": "OPEN_APP", "target": "cursor"},
    {"action": "OPEN_LAST_PROJECT"}
  ],
  "CREATE_PROJECT": [
    {"action": "OPEN_APP", "target": "cursor"},
    {"action": "CREATE_FOLDER", "target": "projects/new_project"},
    {"action": "INITIALIZE_PROJECT"}
  ],
  "RESUME_PROJECT": [
    {"action": "OPEN_APP", "target": "cursor"},
    {"action": "OPEN_RECENT_PROJECT"}
  ],
  "STUDY_MODE": [
    {"action": "CLOSE_DISTRACTIONS"},
    {"action": "OPEN_APP", "target": "notion"},
    {"action": "OPEN_APP", "target": "chrome"},
    {"action": "OPEN_WEBSITE", "target": "youtube_study"},
    {"action": "SET_TIMER", "duration": 50}
  ],
  "FOCUS_MODE": [
    {"action": "CLOSE_DISTRACTIONS"},
    {"action": "PLAY_MUSIC", "target": "lofi"},
    {"action": "SET_TIMER", "duration": 45}
  ],
  "SEARCH_WEB": [
    {"action": "OPEN_APP", "target": "chrome"},
    {"action": "SEARCH", "target": None}
  ],
  "OPEN_WEBSITE": [
    {"action": "OPEN_APP", "target": "chrome"},
    {"action": "OPEN_URL", "target": None}
  ],
  "PLAY_MUSIC": [
    {"action": "OPEN_APP", "target": "spotify"},
    {"action": "PLAY_MUSIC", "target": None}
  ],
  "STOP_MUSIC": [
    {"action": "STOP_MUSIC"}
  ],
  "SYSTEM_CONTROL": [
    {"action": "SYSTEM_ACTION", "target": None}
  ],
  "FILE_OPERATION": [
    {"action": "FILE_ACTION", "target": None}
  ]
}
