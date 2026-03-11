"""Phone number validator using regex-based heuristics."""

from __future__ import annotations

import logging
import re

from ...models.phone_record import PhoneRecord

logger = logging.getLogger(__name__)

_E164_RE = re.compile(r"^\+?(\d[\s\-\(\)]?){7,15}\d$")

_COUNTRY_CODE_MAP: dict[str, str] = {
    "1": "US/CA",
    "7": "RU",
    "20": "EG",
    "27": "ZA",
    "30": "GR",
    "31": "NL",
    "32": "BE",
    "33": "FR",
    "34": "ES",
    "36": "HU",
    "39": "IT",
    "40": "RO",
    "41": "CH",
    "43": "AT",
    "44": "GB",
    "45": "DK",
    "46": "SE",
    "47": "NO",
    "48": "PL",
    "49": "DE",
    "51": "PE",
    "52": "MX",
    "53": "CU",
    "54": "AR",
    "55": "BR",
    "56": "CL",
    "57": "CO",
    "58": "VE",
    "60": "MY",
    "61": "AU",
    "62": "ID",
    "63": "PH",
    "64": "NZ",
    "65": "SG",
    "66": "TH",
    "81": "JP",
    "82": "KR",
    "84": "VN",
    "86": "CN",
    "90": "TR",
    "91": "IN",
    "92": "PK",
    "93": "AF",
    "94": "LK",
    "95": "MM",
    "98": "IR",
}


def _extract_country_code(digits: str) -> tuple[str | None, str | None]:
    """Try to match a known country code prefix (1–3 digits)."""
    for length in (3, 2, 1):
        prefix = digits[:length]
        if prefix in _COUNTRY_CODE_MAP:
            return prefix, _COUNTRY_CODE_MAP[prefix]
    return None, None


class NumberValidator:
    async def validate(self, number: str) -> PhoneRecord:
        cleaned = re.sub(r"[\s\-\(\)]", "", number)
        digits = cleaned.lstrip("+")

        is_valid = bool(_E164_RE.match(number)) and 7 <= len(digits) <= 15

        country_code: str | None = None
        region: str | None = None

        if is_valid and digits:
            country_code, region = _extract_country_code(digits)

        return PhoneRecord(
            number=number,
            country_code=country_code,
            carrier=None,
            line_type=None,
            is_valid=is_valid,
            region=region,
        )
