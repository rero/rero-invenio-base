# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Celery beat scheduler keeping the scheduled tasks in the database.

The tasks of `CELERY_BEAT_SCHEDULE` are stored in the database of the application, where they can be switched on and
off while beat runs. Beat is started with the scheduler:
``celery --app invenio_app.celery beat --scheduler rero_invenio_base.modules.scheduler.DatabaseScheduler``.
"""

from celery import current_app as current_celery
from celery.utils.log import get_logger
from flask import current_app
from sqlalchemy_celery_beat import DatabaseScheduler as BaseDatabaseScheduler
from sqlalchemy_celery_beat.models import PeriodicTask
from sqlalchemy_celery_beat.schedulers import ModelEntry as BaseModelEntry
from sqlalchemy_celery_beat.session import session_cleanup
from werkzeug.local import LocalProxy

logger = get_logger(__name__)


class ModelEntry(BaseModelEntry):
    """Scheduler entry taken from a database row."""

    @classmethod
    def from_entry(cls, name, Session, app=None, **entry):  # noqa: N803 - the library passes it by this name
        """Store a task of the configuration in the database.

        The configuration is applied to a stored task, whose enabled state stays the one in the database. A new task
        is enabled unless its configuration states ``"enabled": False``.

        :param name: name of the task.
        :param Session: session factory of the scheduler.
        :param app: Celery application.
        :param entry: configuration of the task, as in `CELERY_BEAT_SCHEDULE`.
        :returns: the entry of the stored task.
        """
        session = Session()
        with session_cleanup(session):
            periodic_task = session.query(PeriodicTask).filter_by(name=name).first()
            fields = cls._unpack_fields(session, **entry)
            enabled = fields.pop("enabled", True)
            if periodic_task:
                periodic_task.update(**fields)
            else:
                periodic_task = PeriodicTask(name=name, enabled=enabled, **fields)
            session.add(periodic_task)
            session.commit()
            return cls(periodic_task, app=app, Session=Session)


class DatabaseScheduler(BaseDatabaseScheduler):
    """Celery beat scheduler storing the tasks in the database of the application."""

    Entry = ModelEntry

    def __init__(self, *args, **kwargs):
        """Initialize the scheduler on the database of the application.

        :param app: Celery application.
        :param dburi: database URI, `SQLALCHEMY_DATABASE_URI` by default.
        :param schedule: scheduled tasks, `CELERY_BEAT_SCHEDULE` by default.
        :param lazy: do not set the schedule up.
        """
        app = kwargs["app"]
        if dburi := kwargs.get("dburi") or app.conf.get("SQLALCHEMY_DATABASE_URI"):
            app.conf["beat_dburi"] = dburi
        if schema := kwargs.get("schema") or app.conf.get("CELERY_BEAT_SCHEMA"):
            app.conf["beat_schema"] = schema
        if engine_options := kwargs.get("engine_options") or app.conf.get("CELERY_BEAT_ENGINE_OPTIONS"):
            app.conf["beat_engine_options"] = engine_options
        if schedule := kwargs.get("schedule") or app.conf.get("CELERY_BEAT_SCHEDULE"):
            app.conf["beat_schedule"] = schedule
        super().__init__(*args, **kwargs)

    def install_default_entries(self, data):
        """Install no `celery.backend_cleanup` task: the results expire in the Redis result backend.

        :param data: the schedule, unused.
        """

    def get(self, name):
        """Get a stored task.

        :param name: name of the task.
        :returns: its entry, None if there is none.
        """
        return self.all_as_schedule(all_models=True).get(name)

    def reset(self):
        """Remove all the stored tasks, the disabled ones included."""
        session = self.Session()
        with session_cleanup(session):
            for model in session.query(self.Model).all():
                session.delete(model)
            session.commit()

    def all_as_schedule(self, all_models=False):
        """Get the stored tasks.

        A task that cannot be loaded is logged and left out, so that it does not keep the others from running.

        :param all_models: include the disabled tasks.
        :returns: the entries by task name.
        """
        session = self.Session()
        with session_cleanup(session):
            query = session.query(self.Model)
            if not all_models:
                query = query.filter_by(enabled=True)
            schedules = {}
            for model in query.all():
                try:
                    schedules[model.name] = self.Entry(model, app=self.app, Session=self.Session)
                except Exception:
                    logger.exception("Skipping schedule %r because it could not be loaded", model.name)
            return schedules

    def display_entry(self, entry, prefix="- "):
        """Describe a task.

        :param entry: entry of the task.
        :param prefix: prefix of the description.
        :returns: the description.
        """
        return (
            f"{prefix}{entry.name} = {entry.task} | {entry.schedule!r} | kwargs:{entry.kwargs} | "
            f"enabled:{entry.model.enabled}"
        )

    def display_all(self, prefix="- "):
        """Describe all the stored tasks, sorted by name.

        :param prefix: prefix of each description.
        :returns: the descriptions.
        """
        return [
            self.display_entry(entry=entry, prefix=prefix)
            for _, entry in sorted(self.all_as_schedule(all_models=True).items())
        ]

    def set_entry_enabled(self, name, enable=True):
        """Switch a stored task on or off. An unknown name changes nothing.

        :param name: name of the task.
        :param enable: switch it on, off otherwise.
        """
        if entry := self.get(name):
            entry.model.enabled = entry.enabled = enable
            session = self.Session()
            with session_cleanup(session):
                session.add(entry.model)
                session.commit()

    def set_enable_all(self, enable=True):
        """Switch all the stored tasks on or off.

        :param enable: switch them on, off otherwise.
        """
        for name in self.all_as_schedule(all_models=True):
            self.set_entry_enabled(name=name, enable=enable)


#: Scheduler of the current application, on its database and its scheduled tasks.
current_scheduler = LocalProxy(
    lambda: DatabaseScheduler(
        app=current_celery,
        lazy=True,
        dburi=current_app.config["SQLALCHEMY_DATABASE_URI"],
        schedule=current_app.config.get("CELERY_BEAT_SCHEDULE", {}),
    )
)

__all__ = ("DatabaseScheduler", "ModelEntry", "current_scheduler")
