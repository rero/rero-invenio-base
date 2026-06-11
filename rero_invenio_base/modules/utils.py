# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic utils functions."""

from itertools import islice


def chunk(iterable, size):
    """Split a list of value into a list of chunks.

    :param iterable: an iterator or list to be splitted
    :param size: integer - the chunk size
    :return: an iterator on the chunks

    Example:
        list(chunk([1, 2, 3, 4, 5], 2)) == [(1, 2), (3, 4), (5, )]
    """
    it = iter(iterable)
    while batch := tuple(islice(it, size)):
        yield batch
