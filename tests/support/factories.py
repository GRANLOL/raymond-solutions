import json
from types import SimpleNamespace
from unittest.mock import AsyncMock


def make_message(
    *,
    user_id: int = 1,
    full_name: str = "Test User",
    text: str = "",
    web_app_data=None,
):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id, full_name=full_name),
        text=text,
        web_app_data=SimpleNamespace(data=json.dumps(web_app_data)) if web_app_data is not None else None,
        answer=AsyncMock(),
        answer_document=AsyncMock(),
        bot=SimpleNamespace(send_message=AsyncMock(), send_media_group=AsyncMock()),
    )


def make_callback(*, data: str, user_id: int = 1):
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        answer=AsyncMock(),
        message=SimpleNamespace(
            answer=AsyncMock(),
            edit_text=AsyncMock(),
            edit_reply_markup=AsyncMock(),
            delete=AsyncMock(),
        ),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )


def make_state(*, data=None):
    state = AsyncMock()
    state.get_data.return_value = data or {}
    return state
