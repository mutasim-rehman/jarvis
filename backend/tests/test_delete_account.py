"""Account deletion repository tests."""

import uuid
from unittest.mock import MagicMock

from backend.app.db.repositories import delete_user_account


def test_delete_user_account_executes_all_table_deletes():
    session = MagicMock()
    user_id = uuid.uuid4()
    delete_user_account(session, user_id)
    assert session.execute.call_count == 5
    session.flush.assert_called_once()
