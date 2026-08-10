from horolog.seed_demo import DEMO_INTENTS


def test_demo_intents_cover_the_required_mix() -> None:
    kinds = [i["kind"] for i in DEMO_INTENTS]
    assert kinds.count("habit") >= 1
    assert kinds.count("focus") >= 1
    assert kinds.count("task") >= 2
    assert kinds.count("meeting") >= 1
    assert all("due" in i for i in DEMO_INTENTS if i["kind"] == "task"), (
        "tasks in the demo set must carry a due date, per spec"
    )
