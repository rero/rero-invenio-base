# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Helpers and static package parts for streamed XLSX exports."""

import csv
import struct
import zlib
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from functools import partial
from xml.sax.saxutils import escape

from babel.numbers import get_decimal_symbol, get_group_symbol
from flask import current_app, stream_with_context
from invenio_i18n.ext import current_i18n

MAX_XLSX_ROWS = 1_048_576
MAX_XLSX_COLUMNS = 16_384
MAX_XLSX_COLUMN_WIDTH = 255

ZIP32_VERSION = 20
ZIP32_MAX_VALUE = 0xFFFFFFFE
ZIP32_DATA_DESCRIPTOR_FLAG = 0x0008
ZIP32_UTF8_FLAG = 0x0800
ZIP32_DEFLATED = 8

# ZIP32 file headers and descriptors
_LOCAL_FILE_HEADER = 0x04034B50
_CENTRAL_DIRECTORY_HEADER = 0x02014B50
_DATA_DESCRIPTOR = 0x08074B50
_END_OF_CENTRAL_DIRECTORY = 0x06054B50

CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

ROOT_RELS = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

WORKBOOK_RELS = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

STYLES = b"""<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd"/></numFmts>
<fonts count="2"><font/><font><b/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

EXCEL_EPOCH = datetime(1899, 12, 30, tzinfo=UTC)
INVALID_WORKSHEET_NAME_CHARACTERS = set("[]:*?/\\")


class _Zip32Entry:
    """Metadata required to write one central-directory entry."""

    def __init__(
        self,
        name,
        flags,
        crc,
        compressed_size,
        uncompressed_size,
        offset,
    ):
        """Initialize the ZIP entry metadata."""
        self.name = name
        self.flags = flags
        self.crc = crc
        self.compressed_size = compressed_size
        self.uncompressed_size = uncompressed_size
        self.offset = offset


def _zip_name(name):
    """Encode an archive name and return its general-purpose flags."""
    try:
        return name.encode("ascii"), 0
    except UnicodeEncodeError:
        return name.encode("utf-8"), ZIP32_UTF8_FLAG


def _check_zip32(value, description):
    """Raise when a ZIP field would require ZIP64."""
    if value > ZIP32_MAX_VALUE:
        raise ValueError(f"{description} exceeds the ZIP32 limit.")


def _local_header(name, flags, crc=0, compressed_size=0, uncompressed_size=0):
    """Return a ZIP32 local-file header."""
    return (
        struct.pack(
            "<IHHHHHIIIHH",
            _LOCAL_FILE_HEADER,
            ZIP32_VERSION,
            flags,
            ZIP32_DEFLATED,
            0,
            33,  # 1980-01-01, the earliest date supported by ZIP.
            crc,
            compressed_size,
            uncompressed_size,
            len(name),
            0,
        )
        + name
    )


def _central_directory_entry(entry):
    """Return a ZIP32 central-directory entry."""
    return (
        struct.pack(
            "<IHHHHHHIIIHHHHHII",
            _CENTRAL_DIRECTORY_HEADER,
            ZIP32_VERSION,
            ZIP32_VERSION,
            entry.flags,
            ZIP32_DEFLATED,
            0,
            33,
            entry.crc,
            entry.compressed_size,
            entry.uncompressed_size,
            len(entry.name),
            0,
            0,
            0,
            0,
            0,
            entry.offset,
        )
        + entry.name
    )


class _Zip32Stream:
    """Stream a ZIP32 archive while tracking its directory metadata."""

    def __init__(self, entries, compress_level=6):
        """Initialize the ZIP stream."""
        self.entries = entries
        self.compress_level = compress_level
        self.directory = []
        self.offset = 0

    def __iter__(self):
        """Yield the archive entries followed by the central directory."""
        for archive_name, content in self.entries:
            yield from self._write_entry(archive_name, content)
        yield from self._write_directory()

    def _write_entry(self, archive_name, content):
        """Write one static or streamed archive entry."""
        name, name_flags = _zip_name(archive_name)
        header_offset = self.offset
        _check_zip32(header_offset, "ZIP entry offset")

        if isinstance(content, bytes):
            metadata = yield from self._write_static_entry(name, name_flags, content)
        else:
            metadata = yield from self._write_streamed_entry(name, name_flags, content)

        flags, crc, compressed_size, uncompressed_size = metadata
        self.directory.append(
            _Zip32Entry(
                name=name,
                flags=flags,
                crc=crc,
                compressed_size=compressed_size,
                uncompressed_size=uncompressed_size,
                offset=header_offset,
            )
        )

    def _write_static_entry(self, name, flags, content):
        """Write an entry whose size is known before compression."""
        uncompressed_size = len(content)
        crc = zlib.crc32(content) & 0xFFFFFFFF
        compressor = self._compressor()
        compressed = compressor.compress(content) + compressor.flush()
        compressed_size = len(compressed)
        _check_zip32(uncompressed_size, "ZIP entry size")
        _check_zip32(compressed_size, "Compressed ZIP entry size")

        header = _local_header(
            name,
            flags,
            crc=crc,
            compressed_size=compressed_size,
            uncompressed_size=uncompressed_size,
        )
        yield from self._emit(header)
        yield from self._emit(compressed)
        return flags, crc, compressed_size, uncompressed_size

    def _write_streamed_entry(self, name, name_flags, content):
        """Write an entry whose size becomes known during iteration."""
        flags = name_flags | ZIP32_DATA_DESCRIPTOR_FLAG
        yield from self._emit(_local_header(name, flags))

        crc = 0
        compressed_size = 0
        uncompressed_size = 0
        compressor = self._compressor()
        for chunk in content:
            if not isinstance(chunk, bytes):
                raise TypeError("ZIP entry chunks must be bytes.")
            crc = zlib.crc32(chunk, crc) & 0xFFFFFFFF
            uncompressed_size += len(chunk)
            _check_zip32(uncompressed_size, "ZIP entry size")
            compressed = compressor.compress(chunk)
            compressed_size += len(compressed)
            _check_zip32(compressed_size, "Compressed ZIP entry size")
            yield from self._emit(compressed)

        compressed = compressor.flush()
        compressed_size += len(compressed)
        _check_zip32(compressed_size, "Compressed ZIP entry size")
        yield from self._emit(compressed)

        descriptor = struct.pack(
            "<IIII",
            _DATA_DESCRIPTOR,
            crc,
            compressed_size,
            uncompressed_size,
        )
        yield from self._emit(descriptor)
        return flags, crc, compressed_size, uncompressed_size

    def _write_directory(self):
        """Write the central directory and its final record."""
        directory_offset = self.offset
        _check_zip32(directory_offset, "Central-directory offset")
        for entry in self.directory:
            yield from self._emit(_central_directory_entry(entry))

        directory_size = self.offset - directory_offset
        _check_zip32(directory_size, "Central-directory size")
        if len(self.directory) > 0xFFFF:
            raise ValueError("The archive contains too many ZIP32 entries.")

        yield from self._emit(
            struct.pack(
                "<IHHHHIIH",
                _END_OF_CENTRAL_DIRECTORY,
                0,
                0,
                len(self.directory),
                len(self.directory),
                directory_size,
                directory_offset,
                0,
            )
        )

    def _compressor(self):
        """Create a raw DEFLATE compressor."""
        return zlib.compressobj(self.compress_level, zlib.DEFLATED, -zlib.MAX_WBITS)

    def _emit(self, content):
        """Yield non-empty bytes and advance the archive offset."""
        if content:
            self.offset += len(content)
            yield content


def stream_zip32(entries, compress_level=6):
    """Yield a ZIP32 archive without buffering streamed entries."""
    yield from _Zip32Stream(entries, compress_level)


def workbook_xml(worksheet_name):
    """Return the workbook part declaring one validated worksheet."""
    validate_worksheet_name(worksheet_name)
    name = escape(worksheet_name, {'"': "&quot;"})
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<bookViews><workbookView/></bookViews>
<sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets>
</workbook>""".encode()


def validate_worksheet_name(worksheet_name):
    """Raise ``ValueError`` when a worksheet name is not accepted by Excel."""
    if not worksheet_name or len(worksheet_name) > 31:
        raise ValueError("Worksheet names must contain between 1 and 31 characters.")
    if worksheet_name.startswith("'") or worksheet_name.endswith("'"):
        raise ValueError("Worksheet names cannot start or end with an apostrophe.")
    if any(character in INVALID_WORKSHEET_NAME_CHARACTERS for character in worksheet_name):
        raise ValueError("Worksheet names cannot contain []:*?/\\ characters.")
    if clean_xml_text(worksheet_name) != worksheet_name:
        raise ValueError("Worksheet names cannot contain XML control characters.")


def column_ref(index):
    """Return spreadsheet column letters for a zero-based index."""
    if not 0 <= index < MAX_XLSX_COLUMNS:
        raise ValueError(f"XLSX worksheets support at most {MAX_XLSX_COLUMNS} columns.")
    reference = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        reference = chr(65 + remainder) + reference
    return reference


def column_width(value):
    """Return a column width that fits its header within Excel's limit."""
    return min(len(str(value)) + 4, MAX_XLSX_COLUMN_WIDTH)


def excel_serial(value):
    """Return an Excel serial number for an ISO date or datetime."""
    value = str(value).strip()
    try:
        parsed = datetime.fromisoformat(value) if "T" in value else date.fromisoformat(value)
    except ValueError:
        return None

    if isinstance(parsed, datetime):
        parsed = parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    else:
        parsed = datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)

    delta = parsed - EXCEL_EPOCH
    serial = Decimal(delta.days)
    serial += Decimal(delta.seconds) / Decimal(86_400)
    serial += Decimal(delta.microseconds) / Decimal(86_400_000_000)
    return format(serial.normalize(), "f")


def clean_xml_text(value):
    """Replace characters forbidden by XML 1.0 with a replacement marker."""
    characters = []
    for character in str(value):
        codepoint = ord(character)
        if (
            character in "\t\n\r"
            or 0x20 <= codepoint <= 0xD7FF
            or 0xE000 <= codepoint <= 0xFFFD
            or 0x10000 <= codepoint <= 0x10FFFF
        ):
            characters.append(character)
        else:
            characters.append("\ufffd")
    return "".join(characters)


def _excel_number(value, decimal_separator, thousands_separator):
    """Return an Excel-compatible number or ``None``."""
    number = str(value).strip()
    number = number.replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    number = number.replace("\u2019", "").replace("'", "")
    if "," in number:
        if "." in number:
            if number.rfind(",") > number.rfind("."):
                number = number.replace(".", "").replace(",", ".")
            else:
                number = number.replace(",", "")
        elif decimal_separator == ",":
            number = number.replace(",", ".")
        elif thousands_separator == ",":
            number = number.replace(",", "")
    elif "." in number and thousands_separator == ".":
        number = number.replace(".", "")
    try:
        decimal = Decimal(number)
    except InvalidOperation:
        return None
    if not decimal.is_finite():
        return None
    return str(decimal)


class XLSX:
    """Stream an XLSX workbook from serialized CSV rows.

    The CSV header is consumed during initialization. Data rows remain lazy
    until the workbook is iterated.
    """

    def __init__(
        self,
        csv_rows,
        template,
        locale,
        worksheet_name="Export",
    ):
        """Initialize the workbook and consume the CSV header.

        :param csv_rows: Iterable containing serialized CSV chunks.
        :param template: Jinja template used to render the worksheet XML.
        :param locale: Locale used to interpret localized numbers.
        :param worksheet_name: Name of the worksheet.
        """
        self.rows = iter(csv.reader(csv_rows))
        self.header = [clean_xml_text(value) for value in next(self.rows, [])]
        self.template = template
        self.locale = locale
        self.worksheet_name = worksheet_name
        self._validate()

    def __iter__(self):
        """Yield the streamed XLSX package."""
        yield from stream_zip32(self._package_entries())

    def _validate(self):
        """Validate workbook properties known before streaming."""
        if len(self.header) > MAX_XLSX_COLUMNS:
            raise ValueError(f"XLSX worksheets support at most {MAX_XLSX_COLUMNS} columns.")
        validate_worksheet_name(self.worksheet_name)

    def _validated_rows(self):
        """Yield CSV rows while enforcing XLSX worksheet limits."""
        for row_index, row in enumerate(self.rows, start=2):
            if row_index > MAX_XLSX_ROWS:
                raise ValueError(f"XLSX worksheets support at most {MAX_XLSX_ROWS} rows.")
            if len(row) > len(self.header):
                raise ValueError("A CSV row contains more values than the header.")
            yield row

    def _worksheet_chunks(self):
        """Yield worksheet XML chunks rendered from the CSV rows."""
        context = self._template_context()
        for chunk in self.template.generate(**context):
            yield chunk.encode()

    def _template_context(self):
        """Return the values and helpers exposed to the worksheet template."""
        return {
            "header": self.header,
            "data_generator": self._validated_rows(),
            "refs": [column_ref(index) for index in range(len(self.header))],
            "column_width": column_width,
            "excel_serial": excel_serial,
            "excel_text": clean_xml_text,
            "excel_number": partial(
                _excel_number,
                decimal_separator=get_decimal_symbol(self.locale),
                thousands_separator=get_group_symbol(self.locale),
            ),
        }

    def _package_entries(self):
        """Return the static and streamed OOXML package entries."""
        return (
            ("[Content_Types].xml", CONTENT_TYPES),
            ("_rels/.rels", ROOT_RELS),
            ("xl/workbook.xml", workbook_xml(self.worksheet_name)),
            ("xl/_rels/workbook.xml.rels", WORKBOOK_RELS),
            ("xl/styles.xml", STYLES),
            ("xl/worksheets/sheet1.xml", self._worksheet_chunks()),
        )


def csv_to_xlsx(
    csv_rows,
    template_name,
    worksheet_name="Export",
):
    """Stream serialized CSV rows into an XLSX package.

    :param csv_rows: Iterable containing serialized CSV chunks.
    :param template_name: Jinja template name used for the worksheet XML.
    :param worksheet_name: Name of the worksheet.
    :returns: Request-context-aware iterable of XLSX bytes.
    """
    template = current_app.jinja_env.get_template(template_name)
    xlsx = XLSX(
        csv_rows,
        template,
        current_i18n.locale,
        worksheet_name=worksheet_name,
    )
    return stream_with_context(xlsx)


def xlsx_converter(template_name, worksheet_name="Export"):
    """Create a CSV-to-XLSX converter for a template.

    :param template_name: Jinja template name used for the worksheet XML.
    :param worksheet_name: Name of the worksheet.
    :returns: CSV-to-XLSX converter with the template settings applied.
    """
    return partial(
        csv_to_xlsx,
        template_name=template_name,
        worksheet_name=worksheet_name,
    )
