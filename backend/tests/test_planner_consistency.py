"""Regression tests for the concrete business inconsistencies found in review."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from app.modules.exercises.catalog import Equipment, get_catalog
from app.modules.exercises.generator import SplitType, generate_routine
from app.modules.exercises.models import ExerciseRecommendation, ExercisePreferenceModel
from app.modules.exercises.planner_explanation import explain_routine
from app.modules.exercises.planner_schemas import ExplanationRequest
from app.modules.exercises.recommendations import feedback_examples, learning_status
from app.modules.exercises.training_rules import eligible, fits_day, primary_volume, volume_target
from app.modules.user.models import ExperienceLevel, Goal, UserProfile
from app.modules.rag_core.engine import SearchResult


@pytest.mark.parametrize("level", list(ExperienceLevel))
@pytest.mark.parametrize("split,frequency", [(SplitType.PUSH_PULL_LEGS,3),(SplitType.PUSH_PULL_LEGS,4),(SplitType.PUSH_PULL_LEGS,6),(SplitType.UPPER_LOWER,4),(SplitType.FULL_BODY,3)])
@pytest.mark.parametrize("equipment", [list(Equipment), [Equipment.BODYWEIGHT]])
def test_generator_never_relaxes_level_equipment_roles_or_duplicates(level, split, frequency, equipment):
    result = generate_routine(split, frequency, level, Goal.hypertrophy, equipment)
    catalog = get_catalog()
    for day in result.days:
        identifiers = [item.exercise_id for item in day.exercises]
        assert len(set(identifiers)) == len(identifiers)
        for item in day.exercises:
            ex = catalog[item.exercise_id]
            assert eligible(ex, equipment, level)
            assert fits_day(ex, day.name, day.focus)
    assert result.weekly_sets_per_muscle == primary_volume([day.model_dump() for day in result.days], catalog)
    assert result.volume_target == volume_target(level, Goal.hypertrophy)


def test_two_day_ppl_rejected_instead_of_omitting_legs(client):
    result = client.post('/api/exercises/generate-routine', json={"split":"push_pull_legs","days_per_week":2})
    assert result.status_code == 422
    assert "three" in result.json()["detail"]


def test_canonical_volume_is_available_after_generate_save_reload_and_edit(client):
    generated = client.post('/api/exercises/generate-routine', json={"split":"full_body","days_per_week":3}).json()
    payload = {"split":"full_body","days_per_week":3,"routine":generated}
    saved = client.put('/api/exercises/routine', json=payload)
    assert saved.status_code == 200
    loaded = client.get('/api/exercises/routine').json()["routine"]
    assert loaded["weekly_sets_per_muscle"] == generated["weekly_sets_per_muscle"]
    assert loaded["volume_target"] == {"minimum":6,"maximum":12}
    item = loaded["days"][0]["exercises"][0]
    muscle = item["primary_muscle"]
    item["sets"] += 1
    item["primary_muscle"] = "forged"
    loaded["weekly_volume_per_muscle"] = {"forged":999}
    payload["routine"] = loaded
    edited = client.put('/api/exercises/routine', json=payload).json()["routine"]
    assert edited["weekly_sets_per_muscle"][muscle] == generated["weekly_sets_per_muscle"][muscle] + 1
    assert "forged" not in edited["weekly_sets_per_muscle"]
    assert "weekly_volume_per_muscle" not in edited


def test_legacy_program_is_not_rewritten_and_reports_ineligible_exercises(client, session, test_user):
    from app.modules.exercises.models import SavedRoutine
    raw = {"days":[{"name":"Push A","exercises":[{"exercise_id":"barbell-good-morning","sets":3}]}], "weekly_volume_per_muscle":{"back":999}}
    record = SavedRoutine(user_id=test_user.id, split="push_pull_legs", days_per_week=3, routine=raw)
    session.add(record); session.commit()
    result = client.get('/api/exercises/routine').json()["routine"]
    assert result["weekly_sets_per_muscle"]["hamstrings"] == 3
    assert any("experience" in warning for warning in result["warnings"])
    session.refresh(record)
    assert record.routine == raw


def test_ai_suggestion_shares_equipment_level_session_and_volume_rules(client):
    routine = {"days":[{"name":"Push A","exercises":[{"exercise_id":"push-up","sets":5}]}]}
    result = client.post('/api/exercises/ai-suggest-exercise', json={"routine":routine,"available_equipment":["bodyweight"]})
    assert result.status_code == 200, result.text
    suggestion = result.json()["suggested_exercise"]
    assert suggestion is not None
    ex = get_catalog()[suggestion["exercise_id"]]
    assert eligible(ex,[Equipment.BODYWEIGHT],ExperienceLevel.beginner)
    assert fits_day(ex,"Push A")
    assert result.json()["volume_analysis"]["target"] == {"minimum":6,"maximum":12}


def test_ai_does_not_claim_balanced_when_no_candidate_fits(client):
    result = client.post('/api/exercises/ai-suggest-exercise', json={"routine":{"days":[{"name":"Legs A","exercises":[]}]},"available_equipment":[]})
    assert result.status_code == 200
    assert result.json()["is_all_good"] is False
    assert result.json()["suggested_exercise"] is None


def test_ai_blocks_additions_above_range_and_rejects_unknown_ids(client):
    result = client.post('/api/exercises/ai-suggest-exercise', json={"routine":{"days":[{"exercises":[{"exercise_id":"push-up","sets":12},{"exercise_id":"cable-chest-fly","sets":3}]}]}})
    assert result.status_code == 200
    assert result.json()["suggested_exercise"] is None
    assert "exceed" in result.json()["message"]
    invalid = client.post('/api/exercises/ai-suggest-exercise', json={"routine":{"days":[{"exercises":[{"exercise_id":"invented","sets":3}]}]}})
    assert invalid.status_code == 422


def test_replacement_neutralizes_older_pair_feedback_instead_of_inventing_dislike(session,test_user):
    now=datetime.now(timezone.utc)
    for action,offset in [("liked",0),("replaced",1)]:
        session.add(ExerciseRecommendation(user_id=test_user.id,source_exercise_id="push-up",exercise_id="cable-chest-fly",similarity=.5,features={},feedback=action,feedback_at=now+timedelta(seconds=offset)))
    session.commit()
    assert feedback_examples(session,test_user.id)==[]
    status=learning_status(session,test_user.id)
    assert status["examples"]==status["positive"]==status["negative"]==0


def test_models_trained_with_old_replacement_labels_are_not_activated(session,test_user):
    session.add(ExercisePreferenceModel(user_id=test_user.id,parameters={"version":"exercise-preferences-v1"},metrics={}))
    session.commit()
    assert learning_status(session,test_user.id)["active"] is False


def test_rag_query_mentions_actual_exercises_and_diversifies_pages():
    queries=[]
    class Store:
        def search(self,query,category,k):
            queries.append(query)
            return [SearchResult("Guidance", "Manual.pdf",page,"exercise",.9) for page in [1,1,2,3,4,5]]
    class FailingModel:
        def complete(self,**kwargs): raise RuntimeError("offline")
    for identifier in ["push-up","cable-chest-fly"]:
        body=ExplanationRequest(routine={"days":[{"exercises":[{"exercise_id":identifier,"sets":3}]}]})
        result=explain_routine(body,UserProfile(user_id=1),store=Store(),llm=FailingModel())
        assert len(result.sources)==4
        assert len({(s.source,s.page) for s in result.sources})==4
    assert queries[0]!=queries[1]
    assert get_catalog()["push-up"].name in queries[0]
