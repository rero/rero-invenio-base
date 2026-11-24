# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the database scheduler and its command-line utilities."""

from datetime import timedelta

import pytest
from celery import current_app as current_celery
from click.testing import CliRunner
from flask import current_app

from rero_invenio_base.cli.scheduler import enable_tasks, info, init
from rero_invenio_base.modules.scheduler import ModelEntry, current_scheduler

TASK = "rero_invenio_base.modules.tasks.run_on_worker"


@pytest.fixture(scope="module")
def app_config(app_config):
    """One task switched off in the configuration, one with no enabled state."""
    app_config["CELERY_BEAT_SCHEDULE"] = {
        "indexer": {"task": TASK, "schedule": timedelta(minutes=60), "enabled": False},
        "monitor": {"task": TASK, "schedule": timedelta(minutes=1)},
    }
    return app_config


@pytest.fixture
def scheduler(appctx):
    """Scheduler holding the tasks of the configuration only."""
    current_scheduler.reset()
    current_scheduler.setup_schedule()
    return current_scheduler


def _display(name, freq, enabled):
    return f"- {name} = {TASK} | <freq: {freq}> | kwargs:{{}} | enabled:{enabled}"


INDEXER_OFF = _display("indexer", "1.00 hour", False)
INDEXER_ON = _display("indexer", "1.00 hour", True)
MONITOR_ON = _display("monitor", "1.00 minute", True)


def test_scheduler_stores_the_configuration(scheduler):
    """A task is enabled unless its configuration switches it off."""
    assert scheduler.display_all() == [INDEXER_OFF, MONITOR_ON]
    assert list(scheduler.all_as_schedule()) == ["monitor"]


def test_scheduler_switches_tasks(scheduler):
    """A task is switched on and off, an unknown name changes nothing."""
    scheduler.set_entry_enabled("indexer", True)
    scheduler.set_entry_enabled("unknown", True)
    assert scheduler.display_all() == [INDEXER_ON, MONITOR_ON]
    assert scheduler.get("unknown") is None

    scheduler.set_enable_all(False)
    assert scheduler.all_as_schedule() == {}


def test_scheduler_keeps_result_expiry(scheduler):
    """No cleanup task is stored, and the results still expire in the result backend."""
    expires = current_celery.conf.result_expires
    current_scheduler.setup_schedule()
    assert "celery.backend_cleanup" not in current_scheduler.all_as_schedule(all_models=True)
    assert expires
    assert current_celery.conf.result_expires == expires


def test_scheduler_reset_removes_disabled_tasks(scheduler):
    """A reset removes the disabled tasks too."""
    scheduler.reset()
    assert scheduler.display_all() == []


def test_scheduler_applies_config_changes(scheduler, monkeypatch):
    """A changed schedule reaches the database, the enabled state is kept."""
    scheduler.set_entry_enabled("indexer", True)
    schedule = {**current_app.config["CELERY_BEAT_SCHEDULE"]}
    schedule["indexer"] = {**schedule["indexer"], "schedule": timedelta(minutes=30)}
    monkeypatch.setitem(current_app.config, "CELERY_BEAT_SCHEDULE", schedule)

    current_scheduler.setup_schedule()
    assert current_scheduler.display_all() == [_display("indexer", "30.00 minutes", True), MONITOR_ON]


def test_scheduler_skips_broken_task(scheduler, monkeypatch):
    """A task that cannot be loaded leaves the others scheduled."""
    init_entry = ModelEntry.__init__

    def broken_init(self, model, *args, **kwargs):
        if model.name == "indexer":
            raise RuntimeError("broken task")
        init_entry(self, model, *args, **kwargs)

    monkeypatch.setattr(ModelEntry, "__init__", broken_init)
    assert list(scheduler.all_as_schedule(all_models=True)) == ["monitor"]


def test_scheduler_cli(scheduler):
    """The commands store, switch and display the tasks."""
    runner = CliRunner()
    res = runner.invoke(init, ["--reset", "--verbose"])
    assert res.output.splitlines() == ["Reset DB scheduler!", INDEXER_OFF, MONITOR_ON]

    res = runner.invoke(enable_tasks, ["--all", "--verbose"])
    assert res.output.splitlines() == ["Scheduler tasks enabled:", INDEXER_ON, MONITOR_ON]

    res = runner.invoke(enable_tasks, ["--name", "indexer", "--name", "unknown", "--disable", "--verbose"])
    assert res.output.splitlines() == ["Scheduler tasks enabled:", INDEXER_OFF, "Not found entry: unknown"]

    res = runner.invoke(enable_tasks, ["--name", "unknown"])
    assert res.output.splitlines() == ["Not found entry: unknown"]

    res = runner.invoke(info)
    assert res.output.splitlines() == ["Scheduled tasks:", INDEXER_OFF, MONITOR_ON]
