import base64
import json
import os
import shutil
from pathlib import Path

import pymupdf
import requests
from openai import OpenAI

output_dir = "sample_3_table_pages"
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir)
doc = pymupdf.open("./sample-3.pdf")

for page_index in range(len(doc)):
    page = doc[page_index]
    tabs = page.find_tables()
    if tabs.tables:
        pix = page.get_pixmap(dpi=200)
        pix.save(f"./{output_dir}/{page_index + 1:03}.png")
doc.close()

# png_dir = Path(output_dir)
png_dir = Path("sample_3_pngs")


def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


triage_prompt = """***CRITICAL: RESPOND ONLY IN ENGLISH WITH VALID JSON***
Look at this ESG report page image. Does it contain any of these:
- Revenue figures (any currency, any year)
- CO2 emissions (any scope, any year, in tCO2e or other units)
- Scope 1, Scope 2, or Scope 3 data
- Carbon intensity or other climate metrics

Return ONLY this exact JSON structure with no other text, no markdown, no code fences:

{
    "relevant": true,
    "reason": "Brief one-sentence explanation of why relevant or not",
    "summary": "One sentence describing what's actually on this page",
    "fields_found": ["revenue", "CO2", "Scope 1"]  # empty list if none found
}

Your response must start with { and end with } - no backticks, no commentary."""

client = OpenAI(base_url="http://localhost:8080/v1", api_key="not-needed")

# TRIAGE LOOP
pages = []
for png_path in sorted(png_dir.glob("*.png")):
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
    response = client.chat.completions.create(
        model="local", messages=messages, max_tokens=300, temperature=0.1
    )

    response_text = response.choices[0].message.content

    result = json.loads(response_text)

    page_data = {
        "published_page_num": published_page_number,
        "file_path_page_num": file_path_page_number,
        "path": str(png_path),
        "relevant": result.get("relevant"),  # filled in during triage
        "reason": result.get("reason"),
        "summary": result.get("summary"),
        "fields_found": result.get("fields_found", []),
    }
    pages.append(page_data)
    print(response_text)

# EXTRACTION LOOP
relevant_pages = [page for page in pages if page["relevant"]]
for page in relevant_pages:
    published_page_number = page["published_page_num"]
    file_page_number = page["file_path_page_num"]
    fields_on_page = page["fields_found"]
    img_path = page["path"]
