import re
import operator
from pathlib import Path

from .consts import INVENTORY_FIELDNAMES
from .filetypes import CommentedCsvReader


fieldn_pattern = (
    "^(?P<keyword>" + "|".join(fieldn for fieldn in INVENTORY_FIELDNAMES) + ")"
)
value_pattern = r"(?P<value>\S+)$"
field_value_reg = re.compile(fieldn_pattern + "=" + value_pattern)
file_reg = re.compile(r"@(?P<filename>.+)$")
wordsep_re = re.compile(r"\s+|,")


def mk_op_filter(_reg, _fieldn):
    def op_filter(rec):
        return _reg.match(rec[_fieldn])

    op_filter.__doc__ = f"limit_{_fieldn}({_reg.pattern})"
    op_filter.__name__ = op_filter.__doc__
    op_filter.__qualname__ = op_filter.__doc__

    return op_filter


def create_filter_function(op_filters, optest_fn):
    def filter_fn(rec):
        for op_fn in op_filters:
            if optest_fn(op_fn(rec)):
                return False

        return True

    return filter_fn


def mk_file_filter(filepath):

    if filepath.endswith(".csv"):
        filter_hostnames = [rec["host"] for rec in CommentedCsvReader(open(filepath))]

    else:
        filter_hostnames = list()
        with open(filepath) as infile:
            for line_item in infile.readlines():
                if line_item.startswith("#"):
                    continue
                host = iter(next(wordsep_re.split(line_item), None))
                if not host:
                    continue
                filter_hostnames.append(host)

    def op_filter(rec):
        return rec["host"] in filter_hostnames

    op_filter.__doc__ = f"file: {filepath})"
    op_filter.__name__ = op_filter.__doc__
    op_filter.__qualname__ = op_filter.__doc__

    return op_filter


def create_filter(constraints, include=True):
    op_filters = list()
    for filter_expr in constraints:

        # check for the '@<filename>' filtering use-case first.

        if mo := file_reg.match(filter_expr):
            filepath = mo.group(1)
            if not Path(filepath).exists():
                raise FileNotFoundError(filepath)
            op_filters.append(mk_file_filter(filepath))
            continue

        # next check for keyword=value filtering use-case

        if (mo := field_value_reg.match(filter_expr)) is None:
            raise ValueError(f"Invalid filter expression: {filter_expr}")

        fieldn, value = mo.groupdict().values()

        try:
            value_reg = re.compile(f"^{value}$", re.IGNORECASE)

        except re.error as exc:
            raise ValueError(f"Invalid filter expression: {filter_expr}: {str(exc)}")

        op_filters.append(mk_op_filter(value_reg, fieldn))

    optest_fn = operator.not_ if include else operator.truth
    filter_fn = create_filter_function(op_filters, optest_fn)
    filter_fn.op_filters = op_filters
    filter_fn.constraints = constraints

    return filter_fn
