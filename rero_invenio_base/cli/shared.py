# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Command-line utilities shared functions."""


def abort_if_false(ctx, param, value):
    """Abort command if value is False.

    :param ctx: Click context object
    :param param: Click parameter object
    :param value: Boolean value to check
    """
    if not value:
        ctx.abort()
