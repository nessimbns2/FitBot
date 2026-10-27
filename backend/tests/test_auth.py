"""
Authentication, per-user data isolation, privacy and AI-error-handling tests.
"""

from __future__ import annotations

import pytest

from app.core.privacy import redact_pii, validate_llm_output
from app.modules.rag_core.engine import (
    FakeEmbedder,
    FakeLLMClient,
    GeminiLLMClient,
    LLMUnavailableError,
    VectorStore,
    classify_llm_error,
    set_llm_client,
    set_vector_store,
)
from tests.conftest import TEST_EMAIL, TEST_PASSWORD

NEW_USER = {"full_name": "Sara Ben Ali", "email": "Sara@Example.com", "password": "Secret-pass-42"}


def _register(anon_client, **overrides):
    return anon_client.post("/api/auth/register", json={**NEW_USER, **overrides})


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Registration & login ──────────────────────────────────────────────────────


def test_register_returns_token_and_normalized_user(anon_client):
    res = _register(anon_client)
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "sara@example.com"
    assert "password" not in str(body).lower().replace("password_", "")


def test_register_creates_default_profile(anon_client):
    token = _register(anon_client).json()["access_token"]
    res = anon_client.get("/api/user/profile", headers=_bearer(token))
    assert res.status_code == 200
    assert res.json()["weight_kg"] == 75.0


def test_register_duplicate_email_is_409(anon_client):
    assert _register(anon_client).status_code == 201
    res = _register(anon_client, email="SARA@example.com")
    assert res.status_code == 409


@pytest.mark.parametrize(
    "password",
    ["short1", "onlyletters", "1234567890", "x" * 70 + "1é"],  # too short, no digit, no letter, > 72 bytes
)
def test_register_rejects_weak_passwords(anon_client, password):
    assert _register(anon_client, password=password).status_code == 422


def test_register_rejects_invalid_email(anon_client):
    assert _register(anon_client, email="not-an-email").status_code == 422


def test_login_success_and_me(anon_client, test_user):
    res = anon_client.post("/api/auth/login", json={"email": TEST_EMAIL.upper(), "password": TEST_PASSWORD})
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = anon_client.get("/api/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["email"] == TEST_EMAIL
    assert me.json()["last_login_at"] is not None


@pytest.mark.parametrize(
    "email,password",
    [(TEST_EMAIL, "Wrong-pass-123"), ("nobody@example.com", TEST_PASSWORD)],
)
def test_login_failure_is_generic_401(anon_client, test_user, email, password):
    res = anon_client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password."


# ── Protection of the API ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,url",
    [
        ("get", "/api/user/profile"),
        ("get", "/api/user/sessions"),
        ("get", "/api/exercises/catalog"),
        ("get", "/api/overload/volume"),
        ("get", "/api/nutrition/meals"),
        ("get", "/api/exercises/routine"),
        ("get", "/api/auth/me"),
    ],
)
def test_protected_endpoints_require_token(anon_client, method, url):
    res = getattr(anon_client, method)(url)
    assert res.status_code == 401


def test_invalid_and_tampered_tokens_are_rejected(anon_client, auth_headers):
    assert anon_client.get("/api/auth/me", headers=_bearer("garbage")).status_code == 401
    token = auth_headers["Authorization"].split()[1]
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    assert anon_client.get("/api/auth/me", headers=_bearer(tampered)).status_code == 401


def test_health_stays_public(anon_client):
    assert anon_client.get("/api/health").status_code == 200
    ready = anon_client.get("/api/health/ready").json()
    assert ready["database"] == "ok"
    assert ready["database_engine"] == "sqlite"


# ── Account management ────────────────────────────────────────────────────────


def test_update_name_and_change_password(client, anon_client):
    assert client.put("/api/auth/me", json={"full_name": "  New   Name "}).json()["full_name"] == "New Name"

    bad = client.post("/api/auth/change-password", json={"current_password": "nope", "new_password": "Another-pass-9"})
    assert bad.status_code == 400
    ok = client.post("/api/auth/change-password", json={"current_password": TEST_PASSWORD, "new_password": "Another-pass-9"})
    assert ok.status_code == 204

    assert anon_client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}).status_code == 401
    assert anon_client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "Another-pass-9"}).status_code == 200


def test_delete_account_removes_all_personal_data(client, anon_client, session, test_user):
    from sqlmodel import select

    from app.modules.nutrition.models import MealLog
    from app.modules.user.models import UserProfile

    client.post("/api/nutrition/meals", json={"meal_name": "Oats", "calories": 350, "slot": "Breakfast"})
    client.post("/api/overload/log-set", json={"exercise_id": "barbell-bench-press", "reps": 8, "weight": 60})

    assert client.request("DELETE", "/api/auth/me", json={"password": "wrong"}).status_code == 400
    assert client.request("DELETE", "/api/auth/me", json={"password": TEST_PASSWORD}).status_code == 204

    session.expire_all()
    assert session.exec(select(MealLog)).all() == []
    assert session.exec(select(UserProfile)).all() == []
    assert anon_client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}).status_code == 401


# ── Per-user isolation ────────────────────────────────────────────────────────


def test_users_cannot_see_each_other_data(client, anon_client):
    other = _bearer(_register(anon_client).json()["access_token"])

    client.put("/api/user/profile", json={"weight_kg": 90})
    meal = client.post("/api/nutrition/meals", json={"meal_name": "Steak", "calories": 700}).json()
    client.put("/api/exercises/routine", json={"split": "upper_lower", "days_per_week": 4, "routine": {"days": []}})

    assert anon_client.get("/api/user/profile", headers=other).json()["weight_kg"] == 75.0
    assert anon_client.get("/api/nutrition/meals", headers=other).json() == []
    assert anon_client.delete(f"/api/nutrition/meals/{meal['id']}", headers=other).status_code == 404
    assert anon_client.get("/api/exercises/routine", headers=other).json() is None


def test_chat_session_of_another_user_is_404(client, anon_client, mock_llm_and_store):
    sess_id = client.post("/api/chat", json={"message": "How do I squat deeper?"}).json()["session_id"]
    other = _bearer(_register(anon_client).json()["access_token"])
    assert anon_client.get(f"/api/user/sessions/{sess_id}/messages", headers=other).status_code == 404
    res = anon_client.post("/api/chat", json={"message": "hi", "session_id": sess_id}, headers=other)
    assert res.status_code == 404


# ── Meals & routine persistence (replaces browser localStorage) ───────────────


def test_meal_diary_crud(client):
    created = client.post(
        "/api/nutrition/meals",
        json={
            "meal_name": "Chicken bowl",
            "slot": "Lunch",
            "calories": 640,
            "protein_g": 48,
            "carbs_g": 70,
            "fat_g": 16,
            "food_items": [{"name": "Chicken", "portion_est": "180g", "calories": 300}],
        },
    )
    assert created.status_code == 201
    meals = client.get("/api/nutrition/meals").json()
    assert len(meals) == 1 and meals[0]["food_items"][0]["name"] == "Chicken"
    assert client.delete(f"/api/nutrition/meals/{created.json()['id']}").status_code == 204
    assert client.get("/api/nutrition/meals").json() == []


def test_saved_routine_roundtrip(client):
    assert client.get("/api/exercises/routine").json() is None
    routine = {"split": "push_pull_legs", "days": [{"name": "Push", "exercises": []}]}
    res = client.put("/api/exercises/routine", json={"split": "push_pull_legs", "days_per_week": 3, "routine": routine})
    assert res.status_code == 200
    loaded = client.get("/api/exercises/routine").json()["routine"]
    assert loaded["days"] == routine["days"]
    assert loaded["volume_target"] == {"minimum": 6, "maximum": 12}
    assert loaded["weekly_sets_per_muscle"]["chest"] == 0
    assert client.put("/api/exercises/routine", json={"split": "x", "days_per_week": 3, "routine": {}}).status_code == 422
    assert client.delete("/api/exercises/routine").status_code == 204
    assert client.get("/api/exercises/routine").json() is None


# ── Privacy guardrails ────────────────────────────────────────────────────────


def test_redact_pii_masks_identifiers_but_keeps_training_numbers():
    text = "I'm Sara Ben Ali, sara@mail.com, +216 22 123 456. Bench 100 100 95 kg on 2026-10-25, 2500 kcal."
    out = redact_pii(text, known_names=["Sara Ben Ali"])
    assert "sara@mail.com" not in out and "[email]" in out
    assert "22 123 456" not in out and "[phone]" in out
    assert "Sara" not in out and "[name]" in out
    assert "100 100 95" in out and "2026-10-25" in out and "2500" in out


def test_validate_llm_output_strips_scripts_and_prompt_leaks():
    assert validate_llm_output("Hi <script>alert(1)</script>there\nSYSTEM: secret") == "Hi alert(1)there"
    assert validate_llm_output("   ", fallback="fb") == "fb"


def test_chat_never_sends_raw_pii_to_llm(client, mock_llm_and_store):
    client.post("/api/chat", json={"message": "I'm Test Athlete, mail me at a.b@gmail.com about squats"})
    sent = " ".join(m["content"] for m in mock_llm_and_store.calls[-1])
    assert "a.b@gmail.com" not in sent and "Athlete" not in sent
    assert "[email]" in sent


def test_chat_includes_conversation_history(client, mock_llm_and_store):
    sid = client.post("/api/chat", json={"message": "first question about squats"}).json()["session_id"]
    client.post("/api/chat", json={"message": "and a follow-up", "session_id": sid})
    sent = mock_llm_and_store.calls[-1]
    assert [m["content"] for m in sent][-1] == "and a follow-up"
    assert any("first question" in m["content"] for m in sent[:-1])


# ── AI error handling (timeout, quota, missing key) ───────────────────────────


def test_missing_api_key_raises_typed_error():
    with pytest.raises(LLMUnavailableError) as exc:
        GeminiLLMClient(api_key="").complete([{"role": "user", "content": "hi"}], system="s")
    assert exc.value.reason == "missing_api_key"


@pytest.mark.parametrize(
    "exc,reason",
    [
        (type("ResourceExhausted", (Exception,), {})("429 quota"), "quota_exceeded"),
        (type("DeadlineExceeded", (Exception,), {})("deadline"), "timeout"),
        (TimeoutError("timed out"), "timeout"),
        (Exception("API key not valid. Please pass a valid API key."), "invalid_api_key"),
        (RuntimeError("boom"), "provider_error"),
    ],
)
def test_llm_errors_are_classified(exc, reason):
    assert classify_llm_error(exc).reason == reason


class _FailingLLM(FakeLLMClient):
    def complete(self, messages, system):
        raise LLMUnavailableError("quota_exceeded")

    async def stream(self, messages, system):
        raise LLMUnavailableError("timeout")
        yield  # pragma: no cover


def test_chat_degrades_gracefully_when_llm_fails(client, mock_llm_and_store):
    set_llm_client(_FailingLLM())
    res = client.post("/api/chat", json={"message": "How much protein should I eat?"})
    assert res.status_code == 200
    body = res.json()
    assert body["ai_status"] == "quota_exceeded"
    assert "quota" in body["answer"].lower()

    stream = client.post("/api/chat/stream", json={"message": "How much protein should I eat?"})
    assert stream.status_code == 200
    assert "took too long" in stream.text


# ── Rate limiting ─────────────────────────────────────────────────────────────


def test_login_is_rate_limited(anon_client, test_user):
    from app.core.rate_limit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            anon_client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "Wrong-pass-1"}).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:10] == [401] * 10
    assert 429 in codes[10:]


# ── Fixtures ──────────────────────────────────────────────────────────────────


class _RecordingLLM(FakeLLMClient):
    def __init__(self):
        super().__init__("Coach answer [1].")
        self.calls: list[list[dict]] = []

    def complete(self, messages, system):
        self.calls.append(list(messages))
        return super().complete(messages, system)


@pytest.fixture
def mock_llm_and_store(tmp_path):
    set_vector_store(VectorStore(vectorstore_dir=tmp_path, embedder=FakeEmbedder()))
    llm = _RecordingLLM()
    set_llm_client(llm)
    yield llm
    set_llm_client(None)  # type: ignore[arg-type]
    set_vector_store(None)  # type: ignore[arg-type]


def test_llm_fallbacks_share_one_time_budget(monkeypatch):
    """Fallback models never multiply the wait: the whole call stays within LLM_TIMEOUT_SECONDS."""
    import time as _time

    attempts: list[float] = []

    class _SlowModel:
        def generate_content(self, prompt, request_options=None, **kwargs):
            attempts.append(request_options["timeout"])
            _time.sleep(0.6)
            raise type("DeadlineExceeded", (Exception,), {})("504 deadline")

    client = GeminiLLMClient(api_key="test-key")
    client.timeout = 3.0
    monkeypatch.setattr(client, "_get_client", lambda model=None: _SlowModel())

    start = _time.monotonic()
    with pytest.raises(LLMUnavailableError) as exc:
        client.complete([{"role": "user", "content": "hi"}], system="s")
    assert exc.value.reason == "timeout"
    assert _time.monotonic() - start < 3.0
    assert attempts[0] <= 3.0 and all(b < a for a, b in zip(attempts, attempts[1:]))
