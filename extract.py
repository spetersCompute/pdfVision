import base64
import json
import os
import shutil
from pathlib import Path

import pymupdf
import requests
from openai import OpenAI


def render_pdf_to_pngs(pdf_path, dpi, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)

    for page_index in range(total_pages):
        page = doc[page_index]
        output_path = f"./{output_dir}/{page_index + 1:03}.png"

        if not os.path.exists(output_path):
            pix = page.get_pixmap(dpi=dpi)
            pix.save(output_path)
            print(f"Saved page {page_index + 1} to {output_dir}")

    doc.close()
    print(f"All {total_pages} pages converted to {output_dir}")

    return Path(output_dir)


pdf_path = "./sample-3.pdf"
pdf_stem = Path(pdf_path).stem

triage_dpi = 125
extract_dpi = 250

triage_dir = render_pdf_to_pngs(
    pdf_path=pdf_path,
    dpi=triage_dpi,
    output_dir=f"{pdf_stem}_triage_pngs_{triage_dpi}dpi",
)

extract_dir = render_pdf_to_pngs(
    pdf_path=pdf_path,
    dpi=extract_dpi,
    output_dir=f"{pdf_stem}_extract_pngs_{extract_dpi}dpi",
)


def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


triage_prompt = """***CRITICAL: RESPOND ONLY IN ENGLISH WITH VALID JSON***
Return ONLY valid JSON. No markdown. No code fences. No explanation.

You are given an ESG report page image.

Your task is TRIAGE ONLY.

Decide whether this page contains information that could help fill any of these target CSV fields:

- reporting_year (most recent year, Y0)
- financial_year_end
- revenue / turnover
- currency
- scope1
- scope2
- scope3
- scope3_categories

Count a page as relevant if it contains:
- direct values for any of the target fields, OR
- a structured table or KPI section showing those metrics for one or more years, OR
- reporting period text such as "year ended 31 December 2024" or similar wording, OR
- financial year end appearing in text, table notes, footnotes, appendix notes, or reporting-basis sections, OR
- Scope 3 category coverage or an explicit count of Scope 3 categories.

Prefer pages that:
- contain structured tables (KPI tables, appendix tables, emissions tables, economic performance tables)
- contain multiple years (e.g., 2024, 2023, 2022)

Do NOT count a page as relevant if it only contains:
- narrative discussion without extractable numeric values
- project-level, segment-level, or case-study data instead of company totals
- environmental metrics unrelated to targets (water, waste, NOx, SO2, training, safety, etc.)
- sub-rows or breakdowns without the main metric row

Important:
- "turnover" should be treated as revenue
- years may include any visible years (not limited to 2024/2023/2022)
- scope2 is valid even if "market-based" is not explicitly written
- only mark scope3_categories if a count or clear category coverage is shown

Return EXACTLY this structure:

{
  "relevant": true,
  "reason": "one short sentence",
  "fields_present": [
    "reporting_year",
    "financial_year_end",
    "revenue",
    "currency",
    "scope1",
    "scope2",
    "scope3",
    "scope3_categories"
  ],
  "page_type": "table|text|mixed|none"
}

Rules:
- Use relevant=false if none of the target fields are present
- fields_present must only include valid field names
- If not relevant, return:

{
  "relevant": false,
  "reason": "brief reason",
  "fields_present": [],
  "page_type": "none"
}
"""

client = OpenAI(base_url="http://localhost:8080/v1", api_key="not-needed")

# TRIAGE LOOP
pages = []
for png_path in sorted(triage_dir.glob("*.png")):
    published_page_number = int(png_path.stem) - 2
    file_path_page_number = int(png_path.stem)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(png_path)}"
                    },
                },
                {"type": "text", "text": triage_prompt},
            ],
        }
    ]
    print(f"TRIAGE page {file_path_page_number}")
    response = client.chat.completions.create(
        model="local", messages=messages, max_tokens=1000, temperature=0.1
    )

    response_text = response.choices[0].message.content
    print("RAW MODEL RESPONSE:")
    print(repr(response_text))

    if not response_text or not response_text.strip():
        print(f"Empty triage response for file page {file_path_page_number}")
        continue

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        print(f"Invalid triage JSON for file page {file_path_page_number}")
        print(response_text)
        continue

    page_data = {
        "published_page_num": published_page_number,
        "file_path_page_num": file_path_page_number,
        "path": str(png_path),
        "relevant": result.get("relevant"),  # filled in during triage
        "reason": result.get("reason"),
        "fields_present": result.get("fields_present", []),
        "page_type": result.get("page_type", "none"),
    }
    pages.append(page_data)
    print(response_text)

# EXTRACTION LOOP
all_extracted_fields = []
relevant_pages = [page for page in pages if page["relevant"]]
for page in relevant_pages:
    published_page_number = page["published_page_num"]
    file_page_number = page["file_path_page_num"]
    fields_on_page = page["fields_present"]
    img_path = extract_dir / f"{file_page_number:03}.png"

    extraction_prompt = f"""
    Return ONLY valid JSON. No markdown. No code fences. No explanation.

    You are extracting structured ESG metrics from page {published_page_number} of a report.

    The triage stage detected these possible fields on this page:
    {fields_on_page}

    Extract values that correspond to these target metrics:

    - reporting_year (Y0)
    - financial_year_end
    - revenue
    - currency
    - scope1
    - scope2
    - scope3
    - scope3_categories

    Rules:

    TABLE COMPLETENESS (CRITICAL):
    - If a table contains multiple year columns, you MUST extract all visible years for that metric.
    - Do not stop after extracting the most recent year.
    - Do not return a partial set of years from a table.
    - If 5 years are visible in the table, extract all 5 years.
    - Returning only some of the years from a table is an error.
    - When extracting from a table, scan the entire row across all year columns before returning results.


    GENERAL:
    - Extract only from structured tables, KPI summaries, or clearly labeled metric rows.
    - Return one object per field_type and year/value pair.
    - Extract values for visible years, prioritizing the most recent year (Y0) and up to two prior years (Y0-1, Y0-2).
    - Do not prioritize years older than Y0-2.
    - If a table contains a cumulative or total scope-emissions row, collect it for every visible year shown in that row.
    - Collect both the individual scope rows and any cumulative / total scope row in the same table.
    - Do not map a cumulative / total scope row to scope1, scope2, or scope3.
    - Store cumulative / total scope rows as a separate field_type.

    REVENUE:
    - "turnover" is equivalent to revenue.
    - "direct economic value generated" may be treated as revenue only if it clearly represents total company value.
    - Prefer company-level totals over segment, project, subsidiary, or transaction values.
    - Do not extract from assets, equity, investments, loans, or deal-level figures.

    CURRENCY:
    - Extract currency only when clearly associated with revenue.

    FINANCIAL YEAR END:
    - Extract only when an explicit reporting period end date is shown (e.g., "31 December 2024").
    - May appear in main text, footnotes, table notes, appendix, or reporting-basis sections.
    - Do not infer from year alone.

    EMISSIONS:
    - Extract only aggregate rows explicitly labeled:
      - Scope 1
      - Scope 2
      - Scope 3
    - Reject rows combining scopes (e.g., "Scope 1 and Scope 2").
    - Reject totals like "Emissions" or "Total GHG emissions".
    - Do not extract component rows (fuel types, electricity usage, etc.).
    - If both market-based and location-based Scope 2 appear, extract market-based.
    - If only one Scope 2 appears, extract it even if basis is unspecified.
    - Do not extract from narrative text or operational descriptions.

    SCOPE 3 CATEGORIES:
    - Extract only if a numeric count or clear category coverage is explicitly shown.

    QUALITY FILTER:
    - Do not extract from narrative text, case studies, project descriptions, or business activity sections.
    - Ignore pages that only contain headers or labels without values.
    - Omit values that are "/", missing, or unclear.

    STRICTNESS:
    - Do not invent values.
    - Do not modify, convert, or normalize numbers.
    - Preserve value and unit exactly as shown.
    - Do not simplify unit labels.

    Allowed field_type values:
    - "reporting_year"
    - "financial_year_end"
    - "revenue"
    - "currency"
    - "scope1"
    - "scope2"
    - "scope3"
    - "scope3_categories"
    - "scope_total"

    Return exactly this JSON structure:

    {{
      "page": {published_page_number},
      "extracted_fields": [
        {{
          "field_type": "scope1",
          "year": "2024",
          "value": "58046104.46",
          "unit": "tonnes",
          "snippet": "Direct greenhouse gas emissions (Scope 1)",
          "location": "emissions table"
        }}
      ]
    }}
    """

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(img_path)}"
                    },
                },
                {"type": "text", "text": extraction_prompt},
            ],
        }
    ]
    print(f"EXTRACTION page {file_page_number}")
    response = client.chat.completions.create(
        model="local", messages=messages, max_tokens=15000, temperature=0.1
    )
    response_text = response.choices[0].message.content

    print("RAW RESPONSE:")
    print(response_text)
    print("RAW RESPONSE REPR:")
    print(repr(response_text))

    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json") :].strip()
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[len("```") :].strip()

    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3].strip()

    try:
        result = json.loads(cleaned_text)
    except json.JSONDecodeError:
        print(f"Invalid extraction JSON for file page {file_page_number}")
        continue

    for field in result["extracted_fields"]:
        field["page"] = file_page_number

    all_extracted_fields.extend(result["extracted_fields"])
print(json.dumps(all_extracted_fields, indent=2))

cleaned_fields = []

for field in all_extracted_fields:
    value = str(field.get("value", "")).strip()
    location = str(field.get("location", "")).lower()
    snippet = str(field.get("snippet", "")).lower()
    unit = str(field.get("unit", "")).strip()

    # drop missing values
    if value in {"", "/", "N/A", "n/a", "-"}:
        continue

    # drop obvious narrative junk
    if location in {"narrative", "text", "header"} and field["field_type"] in {
        "revenue",
        "scope1",
        "scope2",
        "scope3",
    }:
        continue

    # drop currency-only junk from prose
    if field["field_type"] == "currency" and location in {"narrative", "text"}:
        continue

    cleaned_fields.append(field)

print(json.dumps(cleaned_fields, indent=2))

extracted_candidates_json = json.dumps(cleaned_fields, indent=2)

selection_prompt = f"""
Return ONLY valid JSON. No markdown. No code fences. No explanation.

You are given extracted candidate ESG records from one PDF report.

Your task is to select the records that best correspond to the final CSV output.

Target CSV fields are:
- reporting_year (Y0)
- financial_year_end
- revenue (Y0, Y0-1, Y0-2)
- currency
- scope1 (Y0, Y0-1, Y0-2)
- scope2 (Y0, Y0-1, Y0-2)
- scope3 (Y0, Y0-1, Y0-2)
- scope3_categories

CORE OBJECTIVE:
- Build a complete and consistent dataset for:
  Y0 (most recent year), Y0-1, and Y0-2.

YEAR RULES:
- Identify Y0 from reporting_year or the most recent year present.
- Select values for Y0, Y0-1, and Y0-2 when available.
- Ignore older years (Y0-3 and earlier) unless needed to determine Y0.

PAGE SELECTION:
- Select the minimum set of pages needed to cover:
  - revenue + currency
  - emissions (scope1, scope2, scope3)
  - metadata (reporting_year, financial_year_end)
- These may come from different pages.

PREFERENCE RULES:
- Prefer structured tables over narrative text.
- Prefer appendix/KPI tables over earlier summary tables.
- Prefer pages that contain more years (e.g., 5-year tables over 3-year tables).
- Prefer pages where scope1 and scope2 appear together in the same table.

DEDUPLICATION (CRITICAL):
- If multiple candidate records exist for the same field_type and year:
  - select ONLY ONE best record
  - prefer the record from the most authoritative table
  - prefer records from pages that provide more years (superset tables)
  - drop records from weaker or duplicate pages

MULTI-YEAR COMPLETENESS (CRITICAL):
- If the selected page for revenue contains values for Y0, Y0-1, and Y0-2,
  you MUST include all three years in selected_fields.
- If the selected page for scope1 contains values for Y0, Y0-1, and Y0-2,
  you MUST include all three years in selected_fields.
- If the selected page for scope2 contains values for Y0, Y0-1, and Y0-2,
  you MUST include all three years in selected_fields.
- Do NOT return only the most recent year when prior years exist on the same selected page.
- Returning fewer years than are available on a selected page is an error.

DOMINANCE RULE:
- If two pages contain overlapping values for the same metrics:
  - keep the page that contains more years (superset)
  - drop the page that contains fewer years (subset)

EMISSIONS RULES:
- Reject rows that combine multiple scopes (e.g., "Scope 1 and Scope 2").
- Reject rows labeled only "Emissions" or "Total GHG emissions".
- Prefer rows explicitly labeled:
  - "Scope 1"
  - "Scope 2"
  - "Scope 3"

REVENUE RULES:
- Prefer economic performance tables over narrative mentions.

GENERAL:
- Omit missing values ("/", null, etc).
- Use only candidate records provided.
- Do not invent values.
- Do not modify values.

Return exactly this JSON structure:

{{
    "selected_pages": [121, 122],
  "selected_fields": [
    {{
        "field_type": "revenue",
      "year": "2024",
      "value": "1052.8",
      "unit": "100 million HKD",
      "snippet": "Turnover",
      "location": "Economic performance table",
      "page": 121
    }}
  ]
}}

Candidate records:
{extracted_candidates_json}
"""

selection_messages = [
    {
        "role": "user",
        "content": selection_prompt,
    }
]

selection_response = client.chat.completions.create(
    model="local", messages=selection_messages, max_tokens=5000, temperature=0.1
)

selection_text = selection_response.choices[0].message.content
selection_result = json.loads(selection_text)

print(json.dumps(selection_result, indent=2))
