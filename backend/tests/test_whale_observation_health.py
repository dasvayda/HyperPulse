from concurrent.futures import Future

from scripts.observe_whale_alerts import observation_health


def test_observation_health_stops_claiming_collection_after_completion_or_failure():
    task = Future()
    assert observation_health(task, True)["collecting"] is True
    assert observation_health(task, False)["collecting"] is False
    task.set_result(None)
    assert observation_health(task, True)["observation_status"] == "finished"
    assert observation_health(task, True)["collecting"] is False
    failed = Future()
    failed.set_exception(RuntimeError("collector stopped"))
    assert observation_health(failed, True)["observation_status"] == "failed"
    assert observation_health(failed, True)["collecting"] is False
    cancelled = Future()
    cancelled.cancel()
    assert observation_health(cancelled, True)["observation_status"] == "stopped"
