# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for streamed XLSX exports."""

import struct
from io import BytesIO
from types import SimpleNamespace
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
from babel import Locale
from flask import Flask
from jinja2 import DictLoader

from rero_invenio_base.modules.export import XLSX, csv_to_xlsx, xlsx, xlsx_converter

XLSX_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
    "xl/styles.xml",
    "xl/worksheets/sheet1.xml",
}
XLSX_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLSX_NAMESPACES = {"xlsx": XLSX_NAMESPACE}
XLSX_RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

WORKSHEET_TEMPLATE = """{% set number_columns = ["number", "pid"] %}
{% set date_columns = ["date"] %}
{% set boolean_columns = ["boolean"] %}
{% set state = namespace(rows=0) %}
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0">
    {% if header %}<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>{% endif %}
  </sheetView></sheetViews>
  {% if header %}
  <cols>{% for column in header %}
    <col min="{{ loop.index }}" max="{{ loop.index }}" width="{{ column_width(column) }}" customWidth="1"/>
  {% endfor %}</cols>
  {% endif %}
  <sheetData>
    {% if header %}
    {% set state.rows = 1 %}
    <row r="1">{% for column in header %}
      <c r="{{ refs[loop.index0] }}1" s="1" t="inlineStr"><is><t xml:space="preserve">{{ excel_text(column) }}</t></is></c>
    {% endfor %}</row>
    {% endif %}
    {% for row in data_generator %}
    {% set state.rows = state.rows + 1 %}
    <row r="{{ state.rows }}">{% for column in header %}
      {% set value = row[loop.index0] if loop.index0 < row|length else "" %}
      {% set column_name = column|lower %}
      {% set serial = excel_serial(value) if column_name in date_columns else none %}
      {% set number = excel_number(value) %}
      {% set reference = refs[loop.index0] ~ state.rows %}
      {% if not value %}
      <c r="{{ reference }}"/>
      {% elif serial %}
      <c r="{{ reference }}" s="2"><v>{{ serial }}</v></c>
      {% elif number and column_name in number_columns %}
      <c r="{{ reference }}"><v>{{ number }}</v></c>
      {% elif column_name in boolean_columns %}
      <c r="{{ reference }}" t="b"><v>{{ "1" if value|lower in ["true", "1"] else "0" }}</v></c>
      {% else %}
      <c r="{{ reference }}" t="inlineStr"><is><t xml:space="preserve">{{ excel_text(value) }}</t></is></c>
      {% endif %}
    {% endfor %}</row>
    {% endfor %}
  </sheetData>
  {% if header %}<autoFilter ref="A1:{{ refs[header|length - 1] }}{{ state.rows }}"/>{% endif %}
</worksheet>
"""


def _create_app(locale="en"):
    """Create a minimal application with an active export locale."""
    app = Flask(__name__)
    app.jinja_loader = DictLoader({"worksheet.xml": WORKSHEET_TEMPLATE})
    app.extensions["invenio-i18n"] = SimpleNamespace(locale=Locale.parse(locale))
    return app


def _xlsx_bytes(csv_data, locale="en", worksheet_name="Test"):
    """Convert CSV text to XLSX bytes in a request context."""
    app = _create_app(locale)
    converter = xlsx_converter("worksheet.xml", worksheet_name=worksheet_name)
    with app.test_request_context():
        return b"".join(converter(iter(csv_data.splitlines(keepends=True))))


def _xlsx_parts(raw_data):
    """Return parsed parts from a structurally valid XLSX package."""
    with ZipFile(BytesIO(raw_data)) as archive:
        assert archive.testzip() is None
        assert XLSX_PARTS.issubset(archive.namelist())
        return {part: ElementTree.fromstring(archive.read(part)) for part in XLSX_PARTS}


def _inspect_xlsx(raw_data):
    """Return worksheet metadata and cells parsed directly from OOXML."""
    parts = _xlsx_parts(raw_data)
    workbook = parts["xl/workbook.xml"]
    worksheet = parts["xl/worksheets/sheet1.xml"]
    sheet = workbook.find("xlsx:sheets/xlsx:sheet", XLSX_NAMESPACES)
    pane = worksheet.find("xlsx:sheetViews/xlsx:sheetView/xlsx:pane", XLSX_NAMESPACES)
    auto_filter = worksheet.find("xlsx:autoFilter", XLSX_NAMESPACES)
    widths = [float(column.get("width")) for column in worksheet.findall("xlsx:cols/xlsx:col", XLSX_NAMESPACES)]

    rows = []
    for row in worksheet.findall("xlsx:sheetData/xlsx:row", XLSX_NAMESPACES):
        cells = []
        for cell in row.findall("xlsx:c", XLSX_NAMESPACES):
            cell_type = cell.get("t")
            if cell_type == "inlineStr":
                value = "".join(text.text or "" for text in cell.findall("xlsx:is//xlsx:t", XLSX_NAMESPACES))
                data_type = "s"
            else:
                raw_value = cell.find("xlsx:v", XLSX_NAMESPACES)
                value = (raw_value.text or "") if raw_value is not None else ""
                data_type = "b" if cell_type == "b" else "d" if cell.get("s") == "2" else "n"
            cells.append(
                {
                    "reference": cell.get("r"),
                    "type": data_type,
                    "bold": cell.get("s") == "1",
                    "value": value,
                }
            )
        rows.append(cells)

    return {
        "worksheet_name": sheet.get("name"),
        "freeze_pane": pane.get("topLeftCell") if pane is not None else None,
        "auto_filter": auto_filter.get("ref") if auto_filter is not None else None,
        "widths": widths,
        "rows": rows,
    }


def test_public_xlsx_api_is_exported():
    """Test the XLSX public API is available from the export package."""
    assert XLSX is xlsx.XLSX
    assert csv_to_xlsx is xlsx.csv_to_xlsx
    assert xlsx_converter is xlsx.xlsx_converter


def test_xlsx_converter_streams_csv_rows():
    """Test ZIP bytes are emitted before CSV data rows are consumed."""
    app = _create_app()
    consumed = []

    def csv_rows():
        consumed.append("header")
        yield '"number","date","boolean","identifier","text"\r\n'
        consumed.append("first")
        yield '"23.2","2026-07-29","True","000123","R&D <test>"\r\n'
        consumed.append("second")
        yield '"4","","False","000456","last"\r\n'

    converter = xlsx_converter("worksheet.xml", worksheet_name="Test")
    with app.test_request_context():
        content = iter(converter(csv_rows()))
        assert consumed == ["header"]
        first_chunk = next(content)
        assert first_chunk.startswith(b"PK")
        assert consumed == ["header"]
        raw_data = first_chunk + b"".join(content)

    assert consumed == ["header", "first", "second"]
    workbook = _inspect_xlsx(raw_data)
    assert workbook["worksheet_name"] == "Test"
    assert workbook["freeze_pane"] == "A2"
    assert workbook["auto_filter"] == "A1:E3"
    assert all(cell["bold"] for cell in workbook["rows"][0])
    assert workbook["widths"] == [10, 8, 11, 14, 8]
    assert [cell["type"] for cell in workbook["rows"][1]] == ["n", "d", "b", "s", "s"]
    assert workbook["rows"][-1][-1]["value"] == "last"


def test_xlsx_package_is_complete_zip32():
    """Test static and streamed entries form a complete ZIP32 package."""
    raw_data = _xlsx_bytes('"number"\r\n"2"\r\n')

    with ZipFile(BytesIO(raw_data)) as archive:
        assert archive.testzip() is None
        entries = archive.infolist()
        assert [entry.filename for entry in entries] == [
            "[Content_Types].xml",
            "_rels/.rels",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/styles.xml",
            "xl/worksheets/sheet1.xml",
        ]
        assert all(entry.extract_version == 20 for entry in entries)
        assert all(entry.extra == b"" for entry in entries)
        assert all(entry.flag_bits == 0 for entry in entries[:-1])
        assert entries[-1].flag_bits == xlsx.ZIP32_DATA_DESCRIPTOR_FLAG

        for entry in entries:
            local_header = struct.unpack_from("<IHHHHHIIIHH", raw_data, entry.header_offset)
            assert local_header[1] == 20
            assert 0xFFFFFFFF not in local_header[7:9]
            assert local_header[10] == 0


@pytest.mark.parametrize(
    ("locale", "value", "expected_value"),
    [
        ("en", "1,234", 1234),
        ("fr_CH", "1\u202f234,50", 1234.5),
        ("de", "1.234,50", 1234.5),
        ("de", "1.234", 1234),
        ("de_CH", "1\u2019234.50", 1234.5),
    ],
)
def test_xlsx_number_uses_export_locale(locale, value, expected_value):
    """Test localized numbers use the active export locale."""
    cell = _inspect_xlsx(_xlsx_bytes(f'"number"\r\n"{value}"\r\n', locale))["rows"][1][0]

    assert cell["type"] == "n"
    assert float(cell["value"]) == expected_value


def test_xlsx_number_uses_parsed_decimal_value():
    """Test numeric cells contain the parsed Decimal representation."""
    cell = _inspect_xlsx(_xlsx_bytes('"number"\r\n"1_000"\r\n'))["rows"][1][0]

    assert cell["type"] == "n"
    assert cell["value"] == "1000"


@pytest.mark.parametrize("value", ["invalid", "NaN", "Infinity", "-Infinity"])
def test_xlsx_rejects_invalid_and_non_finite_numbers(value):
    """Test invalid numeric values remain strings."""
    cell = _inspect_xlsx(_xlsx_bytes(f'"number"\r\n"{value}"\r\n'))["rows"][1][0]

    assert cell["type"] == "s"
    assert cell["value"] == value


def test_xlsx_preserves_typed_values_and_missing_cells():
    """Test dates, booleans, strings, empty cells and short rows."""
    value = "  000123 & <catalogue> \x01 é  "
    csv_data = (
        '"pid","date","boolean","identifier","text"\r\n'
        f'"12","2026-07-29T14:30:45.123456+02:00","true","000123","{value}"\r\n'
        '"item1","","false"\r\n'
    )
    rows = _inspect_xlsx(_xlsx_bytes(csv_data))["rows"]

    assert [cell["type"] for cell in rows[1]] == ["n", "d", "b", "s", "s"]
    assert rows[1][1]["value"] == "46232.52135559555555555555556"
    assert rows[1][3]["value"] == "000123"
    assert rows[1][4]["value"] == value.replace("\x01", "\ufffd")
    assert [cell["value"] for cell in rows[2]] == ["item1", "", "0", "", ""]


@pytest.mark.parametrize("worksheet_name", ["", "a" * 32, "'Test", "Test'", "Invalid/name", "Bad\x01name"])
def test_xlsx_rejects_invalid_worksheet_names(worksheet_name):
    """Test invalid worksheet names fail before streaming begins."""
    app = _create_app()
    converter = xlsx_converter("worksheet.xml", worksheet_name=worksheet_name)

    with app.test_request_context(), pytest.raises(ValueError):
        converter(iter(['"number"\r\n']))


def test_xlsx_rejects_too_many_columns(monkeypatch):
    """Test the worksheet column limit is validated from the CSV header."""
    monkeypatch.setattr(xlsx, "MAX_XLSX_COLUMNS", 2)
    app = _create_app()
    converter = xlsx_converter("worksheet.xml")

    with app.test_request_context(), pytest.raises(ValueError, match="at most 2 columns"):
        converter(iter(['"one","two","three"\r\n']))


def test_xlsx_rejects_rows_wider_than_header():
    """Test additional CSV values are never silently dropped."""
    app = _create_app()
    converter = xlsx_converter("worksheet.xml")

    with app.test_request_context(), pytest.raises(ValueError, match="more values"):
        b"".join(converter(iter(['"number"\r\n', '"1","extra"\r\n'])))


def test_xlsx_rejects_rows_over_excel_limit(monkeypatch):
    """Test rows over the worksheet limit are never silently dropped."""
    monkeypatch.setattr(xlsx, "MAX_XLSX_ROWS", 2)
    app = _create_app()
    converter = xlsx_converter("worksheet.xml")

    with app.test_request_context(), pytest.raises(ValueError, match="at most 2 rows"):
        b"".join(converter(iter(['"number"\r\n', '"1"\r\n', '"2"\r\n'])))


def test_column_references_cover_excel_bounds():
    """Test zero-based column indexes are converted to Excel references."""
    assert [xlsx.column_ref(index) for index in [0, 25, 26, xlsx.MAX_XLSX_COLUMNS - 1]] == ["A", "Z", "AA", "XFD"]
    with pytest.raises(ValueError):
        xlsx.column_ref(xlsx.MAX_XLSX_COLUMNS)
