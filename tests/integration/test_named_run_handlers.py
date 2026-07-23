"""Named JobHandler registration and dispatch tests."""

from __future__ import annotations

import pytest

from flask_xxljob import FlaskXXLJob, XXLJobResponse
from flask_xxljob.exceptions import XXLJobCallbackRegistrationError
from tests.conftest import make_app


def _success(content):
    def callback(request):
        return XXLJobResponse.success(content=content)

    return callback


def test_multiple_handlers_dispatch_exactly_and_case_sensitively():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    called = []

    @ext.on_run("demoJobHandler")
    def demo(request):
        called.append("demo")
        return XXLJobResponse.success(content="demo")

    @ext.on_run("reportJobHandler")
    def report(request):
        called.append("report")
        return XXLJobResponse.success(content="report")

    client = app.test_client()
    demo_response = client.post(
        "/run", json={"executorHandler": "demoJobHandler"}
    ).json
    report_response = client.post(
        "/run", json={"executorHandler": "reportJobHandler"}
    ).json
    wrong_case = client.post(
        "/run", json={"executorHandler": "DemoJobHandler"}
    ).json

    assert demo_response["content"] == "demo"
    assert report_response["content"] == "report"
    assert wrong_case == {
        "code": 500,
        "msg": "Unsupported JobHandler: DemoJobHandler",
        "content": None,
    }
    assert called == ["demo", "report"]


@pytest.mark.parametrize(
    ("executor_handler", "display"),
    [("unknown", "unknown"), ("   ", "<empty>")],
)
def test_unknown_and_whitespace_handlers_do_not_dispatch(executor_handler, display):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    called = False

    @ext.on_run("demoJobHandler")
    def handler(request):
        nonlocal called
        called = True
        return XXLJobResponse.success()

    response = app.test_client().post(
        "/run", json={"executorHandler": executor_handler}
    )

    assert response.status_code == 200
    assert response.json["code"] == 500
    assert response.json["msg"] == f"Unsupported JobHandler: {display}"
    assert called is False


def test_long_unknown_handler_is_safely_truncated():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    @ext.on_run("demoJobHandler")
    def handler(request):
        return XXLJobResponse.success()

    value = "sensitive-" + "x" * 200
    response = app.test_client().post(
        "/run", json={"executorHandler": value}
    ).json
    prefix = "Unsupported JobHandler: "
    assert response["msg"].startswith(prefix)
    rendered = response["msg"][len(prefix) :]

    assert response["code"] == 500
    assert len(rendered) == 128
    assert rendered.endswith("...")
    assert value not in response["msg"]


@pytest.mark.parametrize("value", [1, True, [], {}])
def test_non_string_handler_is_rejected_without_dispatch(value):
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    called = False

    @ext.on_run("demoJobHandler")
    def handler(request):
        nonlocal called
        called = True
        return XXLJobResponse.success()

    response = app.test_client().post("/run", json={"executorHandler": value})

    assert response.status_code == 200
    assert response.json["code"] == 500
    assert "executorHandler" in response.json["msg"]
    assert called is False


@pytest.mark.parametrize("name", ["", " ", " demoJobHandler", "demoJobHandler "])
def test_invalid_handler_names_fail_during_registration(name):
    ext = FlaskXXLJob()
    with pytest.raises(XXLJobCallbackRegistrationError):
        ext.on_run(name)


def test_bare_on_run_decorator_is_rejected():
    ext = FlaskXXLJob()

    def handler(request):
        return XXLJobResponse.success()

    with pytest.raises(XXLJobCallbackRegistrationError):
        ext.on_run(handler)  # type: ignore[arg-type]


def test_multiple_deferred_handlers_seed_every_application():
    ext = FlaskXXLJob()
    demo = _success("demo")
    report = _success("report")
    ext.on_run("demoJobHandler")(demo)
    ext.on_run("reportJobHandler")(report)

    app1, _ = make_app(ext, name="named_seed_1")
    app2, _ = make_app(ext, name="named_seed_2")

    for app in (app1, app2):
        assert ext.get_run_callback(app, "demoJobHandler") is demo
        assert ext.get_run_callback(app, "reportJobHandler") is report


def test_register_callbacks_is_atomic_when_a_name_is_invalid():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    with pytest.raises(XXLJobCallbackRegistrationError):
        ext.register_callbacks(
            app,
            run={
                "demoJobHandler": _success("demo"),
                " invalid": _success("invalid"),
            },
            idle_beat=lambda request: XXLJobResponse.success(),
        )

    assert ext.get_run_callback(app, "demoJobHandler") is None
    assert ext.get_idle_beat_callback(app) is None


def test_register_callbacks_is_atomic_on_duplicate_and_replace_is_batch_wide():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)
    original = _success("original")
    ext.set_run_callback(app, "demoJobHandler", original)

    with pytest.raises(XXLJobCallbackRegistrationError):
        ext.register_callbacks(
            app,
            run={
                "newJobHandler": _success("new"),
                "demoJobHandler": _success("duplicate"),
            },
            kill=lambda request: XXLJobResponse.success(),
        )

    assert ext.get_run_callback(app, "demoJobHandler") is original
    assert ext.get_run_callback(app, "newJobHandler") is None
    assert ext.get_kill_callback(app) is None

    replacement = _success("replacement")
    new_callback = _success("new")
    ext.register_callbacks(
        app,
        run={
            "demoJobHandler": replacement,
            "newJobHandler": new_callback,
        },
        replace=True,
    )
    assert ext.get_run_callback(app, "demoJobHandler") is replacement
    assert ext.get_run_callback(app, "newJobHandler") is new_callback


def test_register_callbacks_validates_mapping_and_callback_values():
    ext = FlaskXXLJob()
    app, _ = make_app(ext)

    with pytest.raises(XXLJobCallbackRegistrationError, match="mapping"):
        ext.register_callbacks(app, run=_success("not-a-mapping"))  # type: ignore[arg-type]
    with pytest.raises(XXLJobCallbackRegistrationError, match="callable"):
        ext.register_callbacks(
            app, run={"demoJobHandler": object()}  # type: ignore[dict-item]
        )
