# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic invenio tasks."""

from celery import shared_task


@shared_task()
def run_on_worker(code, fname=None, *args, **kwargs):
    """Run arbitrary code on the celery workers.

    :param code: str - the python code as string
    :param fname: str - the function name to execute, if not specified the
        entire code is executed
    :param args: the parameter list given to the function fname
    :param kwargs: the parameter dict given to the function fname
    :return: the function results if fname is specified, None otherwise

    Usage:
    from rero_invenio_base.modules.tasks import run_on_worker
    from rero_invenio_base.modules.utils import chunk

    Example 1:
    # open a python file containing a `reindex` function
    with open('my_code.py') as f:
        src = f.read()
        for c in chunk([str(val) for val in get_all_ids()], 100):
            run_on_worker.delay(src, 'reindex', c)


    Example 2:
    # python code as string
    code = '''
    def reindex(_ids):
        from rero_ils.modules.documents.api import Document
        n = 0
        errors = []
        for _id in _ids:
            try:
                doc = Document.get_record_by_id(_id)
                doc.reindex()
                n += 1
            except Exception as e:
                print('error', e)
                errors.append(_id)
        return (n, errors)
    '''

    for c in chunk([str(val) for val in get_all_ids()], 100):
        run_on_worker.delay(code, 'reindex', c)

    """
    # compile the code
    compiled = compile(code, "code", "exec")
    # execute the compiled code
    if not fname:
        return exec(compiled)
    # if a given function name is given, execute this function with the given
    # parameters
    functions = {}
    exec(compiled, {}, functions)
    return functions[fname](*args, **kwargs)
