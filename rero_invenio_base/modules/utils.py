# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic utils functions."""

from collections.abc import Iterable, Iterator
from itertools import islice


def chunk[T](iterable: Iterable[T], size: int) -> Iterator[tuple[T, ...]]:
    """Split a list of value into a list of chunks.

    :param iterable: an iterator or list to be splitted
    :param size: integer - the chunk size
    :return: an iterator on the chunks

    Example:
        list(chunk([1, 2, 3, 4, 5], 2)) == [(1, 2), (3, 4), (5, )]
    """
    it = iter(iterable)
    while chunk := tuple(islice(it, size)):
        yield chunk
