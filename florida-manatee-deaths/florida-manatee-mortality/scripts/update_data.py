#!/usr/bin/env python3
"""Build the production mortality.json from official Florida FWC sources.

Sources:
* Recent preliminary individual records: the annual FWC mortality PDF.
* Finalized historical records: the FWC ArcGIS mortality layer.

The script intentionally keeps FWC's preliminary records separate from
finalized ArcGIS records and writes the output atomically only after validation.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pdfplumber


FWC_STATS_URL = (
    "https://myfwc.com/research/manatee/rescue-mortality-response/"
    "statistics/mortality/"
)
FWC_YEAR_URL = FWC_STATS_URL + "{year}/"
ARCGIS_LAYER = (
    "https://gis.myfwc.com/mapping/rest/services/Open_Data/"
    "Manatee_Carcass_Recovery_locations_in_Florida/MapServer/32"
)
USER_AGENT = (
    "Hearst-Manatee-Mortality-Interactive/1.0 "
    "(daily public-data refresh; source attribution in output)"
)
PAGE_SIZE = 2000

CAUSE_GLOSSARY = {
    "Watercraft": "Death caused by a collision with a boat hull or propeller.",
    "Flood Gate/Canal Lock": (
        "Death associated with a flood-control gate or canal lock."
    ),
    "Human-Related, Other": (
        "Other human-related causes, such as entanglement or ingestion of debris."
    ),
    "Perinatal": (
        "A dependent calf 150 cm or shorter that died at or near birth."
    ),
    "Cold Stress": (
        "Death associated with cold-stress syndrome after prolonged cold exposure."
    ),
    "Natural": "Natural causes such as disease, injury, or brevetoxicosis.",
    "Undetermined: Too Decomposed": (
        "Cause could not be determined because of decomposition."
    ),
    "Undetermined: Other": "Cause could not be determined for another reason.",
    "Verified, Not Necropsied": (
        "The death was verified, but a full necropsy was not completed."
    ),
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "a":
            return
        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append(
                {"href": self._href, "text": " ".join(self._text).strip()}
            )
            self._href = None
            self._text = []


def request_bytes(url: str, attempts: int = 3) -> tuple[bytes, dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,text/html,application/pdf,*/*",
                },
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                return response.read(), headers
        except Exception as error:  # pragma: no cover - network retry path
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Could not retrieve {url}: {last_error}")


def request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(params)
    body, _ = request_bytes(f"{url}?{encoded}")
    result = json.loads(body)
    if "error" in result:
        raise RuntimeError(f"FWC ArcGIS error: {result['error']}")
    return result


def discover_preliminary_pdf(year: int) -> str:
    page_url = FWC_YEAR_URL.format(year=year)
    body, _ = request_bytes(page_url)
    parser = LinkParser()
    parser.feed(body.decode("utf-8", errors="replace"))

    candidates: list[str] = []
    for link in parser.links:
        href = link["href"]
        text = link["text"].lower()
        if ".pdf" not in href.lower():
            continue
        if "preliminary" in text and "mortality" in text:
            return urllib.parse.urljoin(page_url, href)
        if href.lower().split("?")[0].endswith("/preliminary.pdf"):
            candidates.append(urllib.parse.urljoin(page_url, href))

    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(
        f"Could not uniquely identify the preliminary mortality PDF for {year}"
    )


def normalize_cause(raw: str) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", raw or "").strip()
    lowered = text.lower()
    if "watercraft" in lowered:
        return "Watercraft", "WC"
    if "flood gate" in lowered or "canal lock" in lowered:
        return "Flood Gate/Canal Lock", "GL"
    if "human related" in lowered or "human-related" in lowered:
        return "Human-Related, Other", "HR"
    if "perinatal" in lowered:
        return "Perinatal", "PN"
    if "cold stress" in lowered:
        return "Cold Stress", "CS"
    if lowered.startswith("natural"):
        return "Natural", "NA"
    if "too decomposed" in lowered:
        return "Undetermined: Too Decomposed", "UD"
    if "undetermined" in lowered:
        return "Undetermined: Other", "UO"
    if "not necropsied" in lowered or "not recovered" in lowered:
        return "Verified, Not Necropsied", "VN"
    raise ValueError(f"Unknown FWC cause label: {text!r}")


def normalize_sex(raw: str | None) -> str:
    value = (raw or "").strip().upper()
    return {"M": "Male", "F": "Female", "U": "Undetermined"}.get(
        value, "Undetermined"
    )


def pdf_word_rows(page: Any) -> list[list[str]]:
    """Read report rows by position so both FWC PDF layouts are supported.

    FWC's 2024 report uses a different table structure after page one, and the
    first record on continuation pages is not exposed as a complete table row.
    The visual column positions, however, are consistent across report years.
    """
    words = page.extract_words(keep_blank_chars=False)
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > 1.5:
            lines.append([word])
        else:
            lines[-1].append(word)

    output: list[list[str]] = []
    for line in lines:
        date_words = [
            word
            for word in line
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", word["text"])
            and 110 <= word["x0"] < 180
        ]
        if len(date_words) != 1:
            continue

        cells = [""] * 8
        for word in line:
            x = word["x0"]
            if x < 110:
                cell = 0  # county
            elif x < 180:
                cell = 1  # date
            elif x < 246:
                cell = 2  # field ID
            elif x < 270:
                cell = 3  # sex
            elif x < 305:
                cell = 4  # length
            elif x < 425:
                cell = 5  # waterway
            elif x < 535:
                cell = 6  # city
            else:
                cell = 7  # probable cause
            cells[cell] = f"{cells[cell]} {word['text']}".strip()

        # Older reports include legacy IDs such as SWFTm2358 and LPZ103707.
        if re.fullmatch(r"[A-Za-z0-9-]{5,}", cells[2]):
            output.append(cells)
    return output


def parse_pdf(
    content: bytes, year: int, source_url: str, fetched_at: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    full_text: list[str] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            full_text.append(page.extract_text() or "")
            for row in pdf_word_rows(page):
                date_text = row[1].strip()
                date_value = datetime.strptime(date_text, "%m/%d/%Y").date()
                if date_value.year != year:
                    raise ValueError(
                        f"Unexpected year in {year} PDF row: {date_text}"
                    )

                cause, cause_code = normalize_cause(row[7])
                length_text = row[4].strip()
                length_cm = (
                    int(float(length_text))
                    if re.fullmatch(r"\d+(?:\.\d+)?", length_text)
                    else None
                )
                records.append(
                    {
                        "fieldId": row[2].strip() or None,
                        "date": date_value.isoformat(),
                        "county": re.sub(r"\s+", " ", row[0]).strip(),
                        "sex": normalize_sex(row[3]),
                        "lengthCm": length_cm,
                        "waterway": re.sub(r"\s+", " ", row[5]).strip() or None,
                        "city": re.sub(r"\s+", " ", row[6]).strip() or None,
                        "cause": cause,
                        "causeCode": cause_code,
                        "latitude": None,
                        "longitude": None,
                        "status": "preliminary",
                        "source": f"Florida FWC preliminary {year} mortality table",
                        "sourceAsOf": None,
                        "fetchedAt": fetched_at,
                    }
                )

    text = "\n".join(full_text)
    period = re.search(
        r"From:\s*(\d{2}/\d{2}/\d{4})\s+To:\s*(\d{2}/\d{2}/\d{4})",
        text,
    )
    if not period:
        raise ValueError(f"Could not find reporting period in {year} PDF")
    source_as_of = datetime.strptime(period.group(2), "%m/%d/%Y").date().isoformat()
    for record in records:
        record["sourceAsOf"] = source_as_of

    summary_match = re.search(r"Total\s*=\s*([\d,]+)\s*\(FL only\)", text)
    published_total = (
        int(summary_match.group(1).replace(",", "")) if summary_match else None
    )
    cause_counts = Counter(record["cause"] for record in records)
    warnings: list[str] = []
    if published_total is not None and published_total != len(records):
        warnings.append(
            f"The {year} FWC PDF prints a statewide total of {published_total:,}, "
            f"but its itemized rows and parsed cause counts total {len(records):,}."
        )
        if abs(published_total - len(records)) > 2:
            raise ValueError(
                f"{year} PDF count mismatch is too large: "
                f"published={published_total}, parsed={len(records)}"
            )

    if not records:
        raise ValueError(f"No mortality rows were parsed from the {year} PDF")
    field_ids = [record["fieldId"] for record in records if record["fieldId"]]
    if len(field_ids) != len(set(field_ids)):
        raise ValueError(f"Duplicate Field IDs found in the {year} PDF")

    return records, {
        "year": year,
        "status": "preliminary",
        "sourceUrl": source_url,
        "sourceAsOf": source_as_of,
        "publishedTotal": published_total,
        "itemizedTotal": len(records),
        "causeCounts": dict(sorted(cause_counts.items())),
        "warnings": warnings,
    }


def arcgis_records(
    start_year: int, end_year: int, fetched_at: str
) -> list[dict[str, Any]]:
    if end_year < start_year:
        return []

    fields = (
        "OBJECTID,FIELDID,REPDATE,REPYEAR,SEX,TLENGTH,STATE,COUNTY,"
        "LAT,LONG_,DCODE,MORTALITY,last_edited_date"
    )
    where = (
        f"STATE = 'FL' AND REPYEAR >= {start_year} AND REPYEAR <= {end_year}"
    )
    offset = 0
    output: list[dict[str, Any]] = []

    while True:
        result = request_json(
            f"{ARCGIS_LAYER}/query",
            {
                "f": "json",
                "where": where,
                "outFields": fields,
                "returnGeometry": "false",
                "orderByFields": "OBJECTID ASC",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
            },
        )
        features = result.get("features", [])
        for feature in features:
            attrs = feature["attributes"]
            if attrs.get("REPDATE") is None:
                continue
            report_date = datetime.fromtimestamp(
                attrs["REPDATE"] / 1000, tz=timezone.utc
            ).date()
            cause, cause_code = normalize_cause(attrs.get("MORTALITY") or "")
            year = int(attrs["REPYEAR"])
            output.append(
                {
                    "fieldId": attrs.get("FIELDID"),
                    "date": report_date.isoformat(),
                    "county": attrs.get("COUNTY"),
                    "sex": normalize_sex(attrs.get("SEX")),
                    "lengthCm": attrs.get("TLENGTH"),
                    "waterway": None,
                    "city": None,
                    "cause": cause,
                    "causeCode": cause_code,
                    "latitude": attrs.get("LAT"),
                    "longitude": attrs.get("LONG_"),
                    "status": "final",
                    "source": "Florida FWC ArcGIS finalized mortality records",
                    "sourceAsOf": f"{year}-12-31",
                    "fetchedAt": fetched_at,
                }
            )

        if len(features) < PAGE_SIZE:
            break
        offset += len(features)

    return output


def build_dataset(
    current_year: int, local_pdfs: dict[int, Path]
) -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pdf_years = list(range(max(1974, current_year - 2), current_year + 1))
    historical_start = max(1974, current_year - 5)
    historical_end = pdf_years[0] - 1

    records = arcgis_records(historical_start, historical_end, fetched_at)
    coverage: list[dict[str, Any]] = []
    warnings: list[str] = []

    if records:
        for year in range(historical_start, historical_end + 1):
            count = sum(record["date"].startswith(f"{year}-") for record in records)
            if count:
                coverage.append(
                    {
                        "year": year,
                        "status": "final",
                        "sourceUrl": ARCGIS_LAYER,
                        "sourceAsOf": f"{year}-12-31",
                        "publishedTotal": None,
                        "itemizedTotal": count,
                        "causeCounts": dict(
                            sorted(
                                Counter(
                                    record["cause"]
                                    for record in records
                                    if record["date"].startswith(f"{year}-")
                                ).items()
                            )
                        ),
                        "warnings": [],
                    }
                )

    for year in pdf_years:
        source_url = discover_preliminary_pdf(year)
        if year in local_pdfs:
            content = local_pdfs[year].read_bytes()
        else:
            content, _ = request_bytes(source_url)
        parsed, report = parse_pdf(content, year, source_url, fetched_at)
        records.extend(parsed)
        coverage.append(report)
        warnings.extend(report["warnings"])

    records.sort(key=lambda record: (record["date"], record["fieldId"] or ""))
    if not records:
        raise ValueError("The combined FWC dataset is empty")

    keys = [
        (record["fieldId"], record["date"])
        for record in records
        if record["fieldId"]
    ]
    if len(keys) != len(set(keys)):
        duplicates = [key for key, count in Counter(keys).items() if count > 1]
        raise ValueError(f"Duplicate records across sources: {duplicates[:5]}")

    counts_by_year = dict(
        sorted(Counter(record["date"][:4] for record in records).items())
    )
    return {
        "_meta": {
            "sample": False,
            "source": (
                "Florida Fish and Wildlife Conservation Commission (FWC), "
                "Fish and Wildlife Research Institute"
            ),
            "sourceUrl": FWC_STATS_URL,
            "fetchedAt": fetched_at,
            "generatedAt": fetched_at,
            "causeGlossary": CAUSE_GLOSSARY,
            "recordCountsByYear": counts_by_year,
            "coverage": sorted(coverage, key=lambda item: item["year"]),
            "warnings": warnings,
            "sourceFeeds": {
                "finalizedArcGIS": ARCGIS_LAYER,
                "annualMortalityPages": {
                    str(year): FWC_YEAR_URL.format(year=year) for year in pdf_years
                },
            },
        },
        "records": records,
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "mortality.json",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Current reporting year; defaults to the current calendar year.",
    )
    parser.add_argument(
        "--pdf",
        action="append",
        default=[],
        metavar="YEAR=PATH",
        help="Use a local PDF for one reporting year while still discovering its URL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    local_pdfs: dict[int, Path] = {}
    for item in args.pdf:
        year_text, separator, path_text = item.partition("=")
        if not separator:
            raise ValueError(f"Invalid --pdf value: {item!r}")
        local_pdfs[int(year_text)] = Path(path_text)

    dataset = build_dataset(args.year, local_pdfs)
    write_json_atomic(args.output, dataset)
    meta = dataset["_meta"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "records": len(dataset["records"]),
                "countsByYear": meta["recordCountsByYear"],
                "warnings": meta["warnings"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"update_data.py failed: {error}", file=sys.stderr)
        raise
