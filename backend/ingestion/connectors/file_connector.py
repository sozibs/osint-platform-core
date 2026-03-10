"""File connector supporting CSV, JSON, XML, JSONL, and Excel formats."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Maximum number of rows to process in a single call (safety limit)
_MAX_ROWS = 1_000_000


class FileConnectorError(Exception):
    """Raised when file ingestion fails."""


class FileConnector:
    """Ingests structured data files: CSV, JSON, JSONL, XML, Excel."""

    SUPPORTED_FORMATS = ["csv", "json", "jsonl", "xml", "xlsx", "xls"]

    # ── CSV ────────────────────────────────────────────────────────────────────

    async def ingest_csv(
        self,
        file_data: bytes,
        mapping: Optional[Dict[str, str]] = None,
        delimiter: str = ",",
        encoding: str = "utf-8",
    ) -> List[Dict[str, Any]]:
        """Parse CSV bytes and return a list of normalized record dicts."""
        try:
            text = file_data.decode(encoding, errors="replace")
        except Exception as exc:
            raise FileConnectorError(f"Cannot decode CSV: {exc}") from exc

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        records: List[Dict[str, Any]] = []
        for i, row in enumerate(reader):
            if i >= _MAX_ROWS:
                logger.warning("CSV row limit (%d) reached; truncating.", _MAX_ROWS)
                break
            records.append(dict(row))

        if mapping:
            records = await self.apply_mapping(records, mapping)
        logger.info("Ingested %d rows from CSV.", len(records))
        return records

    # ── JSON ───────────────────────────────────────────────────────────────────

    async def ingest_json(
        self,
        file_data: bytes,
        array_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Parse JSON bytes.

        If *array_path* is provided (dot-separated), extract the nested list
        at that path. Otherwise the root value must be a list, or the single
        object is wrapped in a list.
        """
        try:
            parsed = json.loads(file_data.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise FileConnectorError(f"Invalid JSON: {exc}") from exc

        if array_path:
            for key in array_path.split("."):
                if isinstance(parsed, dict) and key in parsed:
                    parsed = parsed[key]
                else:
                    raise FileConnectorError(f"array_path '{array_path}' not found in JSON.")

        if isinstance(parsed, list):
            records = [r if isinstance(r, dict) else {"value": r} for r in parsed[:_MAX_ROWS]]
        elif isinstance(parsed, dict):
            records = [parsed]
        else:
            raise FileConnectorError(f"Unexpected JSON root type: {type(parsed)}")

        logger.info("Ingested %d records from JSON.", len(records))
        return records

    # ── JSONL ──────────────────────────────────────────────────────────────────

    async def ingest_jsonl(self, file_data: bytes) -> List[Dict[str, Any]]:
        """Parse JSON Lines (newline-delimited JSON) bytes."""
        records: List[Dict[str, Any]] = []
        text = file_data.decode("utf-8", errors="replace")
        for i, line in enumerate(text.splitlines()):
            if i >= _MAX_ROWS:
                logger.warning("JSONL row limit (%d) reached; truncating.", _MAX_ROWS)
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                records.append(obj if isinstance(obj, dict) else {"value": obj})
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSONL line %d: %s", i + 1, exc)

        logger.info("Ingested %d records from JSONL.", len(records))
        return records

    # ── XML ────────────────────────────────────────────────────────────────────

    async def ingest_xml(
        self,
        file_data: bytes,
        record_tag: str = "record",
        mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Parse XML bytes, extracting elements matching *record_tag*.

        Each element's child text values and attributes become dict fields.
        """
        try:
            root = ET.fromstring(file_data)
        except ET.ParseError as exc:
            raise FileConnectorError(f"Invalid XML: {exc}") from exc

        elements = (
            root.findall(f".//{record_tag}")
            if root.tag != record_tag
            else [root]
        )

        records: List[Dict[str, Any]] = []
        for i, elem in enumerate(elements):
            if i >= _MAX_ROWS:
                logger.warning("XML row limit (%d) reached; truncating.", _MAX_ROWS)
                break
            record: Dict[str, Any] = {}
            # Attributes
            record.update(elem.attrib)
            # Child elements as text
            for child in elem:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                record[tag] = (child.text or "").strip()
            # Own text if no children
            if not list(elem) and elem.text:
                record["text"] = elem.text.strip()
            records.append(record)

        if mapping:
            records = await self.apply_mapping(records, mapping)
        logger.info("Ingested %d records from XML (tag=%s).", len(records), record_tag)
        return records

    # ── Excel ──────────────────────────────────────────────────────────────────

    async def ingest_excel(
        self,
        file_data: bytes,
        sheet_name: Optional[str] = None,
        mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Parse Excel (.xlsx / .xls) bytes using pandas."""
        try:
            loop = asyncio.get_event_loop()
            df: pd.DataFrame = await loop.run_in_executor(
                None,
                lambda: pd.read_excel(
                    io.BytesIO(file_data),
                    sheet_name=sheet_name or 0,
                    dtype=str,
                    keep_default_na=False,
                ),
            )
        except Exception as exc:
            raise FileConnectorError(f"Cannot parse Excel file: {exc}") from exc

        if len(df) > _MAX_ROWS:
            logger.warning("Excel row limit (%d) reached; truncating.", _MAX_ROWS)
            df = df.iloc[:_MAX_ROWS]

        records: List[Dict[str, Any]] = df.to_dict(orient="records")

        if mapping:
            records = await self.apply_mapping(records, mapping)
        logger.info("Ingested %d rows from Excel.", len(records))
        return records

    # ── Format detection ───────────────────────────────────────────────────────

    async def detect_format(self, file_data: bytes, filename: str) -> str:
        """Detect file format from filename extension and content sniffing."""
        name_lower = filename.lower()
        for ext in ("xlsx", "xls", "jsonl", "json", "xml", "csv"):
            if name_lower.endswith(f".{ext}"):
                return ext

        # Content sniffing for ambiguous or missing extensions
        sample = file_data[:512].lstrip()
        if sample.startswith(b"PK\x03\x04"):
            return "xlsx"
        if sample.startswith((b"[", b"{")):
            decoded = sample.decode("utf-8", errors="ignore")
            if decoded.count("\n") > 0 and decoded.lstrip().startswith("{"):
                return "jsonl"
            return "json"
        if sample.startswith(b"<"):
            return "xml"
        # Fallback: assume CSV
        return "csv"

    # ── Mapping ────────────────────────────────────────────────────────────────

    async def apply_mapping(
        self, records: List[Dict[str, Any]], mapping: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Rename / transform fields according to *mapping*.

        Mapping format: ``{source_field: target_field}``.
        Unmapped fields are preserved unless the mapping has ``"*": null``.
        Dot-notation source fields are extracted from nested dicts.
        """
        drop_unmapped = mapping.get("*") is None and "*" in mapping

        def get_nested(record: Dict[str, Any], path: str) -> Any:
            obj: Any = record
            for part in path.split("."):
                if isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    return None
            return obj

        result: List[Dict[str, Any]] = []
        for record in records:
            new_record: Dict[str, Any] = {}
            if not drop_unmapped:
                new_record.update(record)
            for src, dst in mapping.items():
                if src == "*":
                    continue
                value = get_nested(record, src)
                if value is not None and dst:
                    new_record[dst] = value
                    if dst != src and src in new_record:
                        del new_record[src]
            result.append(new_record)
        return result

    # ── Auto-detect and ingest ─────────────────────────────────────────────────

    async def ingest(
        self,
        file_data: bytes,
        filename: str,
        mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Auto-detect format and ingest file, returning normalized records."""
        fmt = await self.detect_format(file_data, filename)
        logger.info("Detected format '%s' for file '%s'.", fmt, filename)

        if fmt == "csv":
            return await self.ingest_csv(file_data, mapping=mapping)
        if fmt == "json":
            records = await self.ingest_json(file_data)
            return await self.apply_mapping(records, mapping) if mapping else records
        if fmt == "jsonl":
            records = await self.ingest_jsonl(file_data)
            return await self.apply_mapping(records, mapping) if mapping else records
        if fmt == "xml":
            return await self.ingest_xml(file_data, mapping=mapping)
        if fmt in ("xlsx", "xls"):
            return await self.ingest_excel(file_data, mapping=mapping)

        raise FileConnectorError(
            f"Unsupported format '{fmt}'. Supported: {self.SUPPORTED_FORMATS}"
        )
