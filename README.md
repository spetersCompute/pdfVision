# PDF Vision

Multi-stage PDF extraction workflow designed to convert complex multi-layout and scanned PDFs into structured data with validation and page-level traceability.

This project explores the use of Vision Language Models (VLMs) as an alternative to traditional OCR-only pipelines for handling difficult real-world document layouts.

---

# Overview

PDF Vision implements a staged workflow for extracting structured data from large, complex PDF documents.

The pipeline is designed to handle:

- Mixed-layout documents  
- Scanned PDFs  
- Multi-hundred-page files  
- Multi-line table records  
- Inconsistent formatting across pages  
- Layout variation between sections  

Instead of relying on a single-pass OCR workflow, this system uses multi-stage processing to improve both efficiency and reliability.

---

# Project Origin

This workflow was developed to satisfy structured data extraction requirements similar to those found in contract-based data processing workflows.

The initial requirements involved:

- Multi-hundred-page PDFs  
- Mixed table layouts  
- Scanned documents  
- Multi-line structured records  
- High-accuracy validation requirements  
- Reliable structured output generation  

A traditional OCR-based workflow was expected.  
Instead, this project explores a modern alternative using **Vision Language Models (VLMs)** to perform layout-aware extraction.

The goal was to determine whether VLM-driven workflows could handle complex layouts while maintaining structured output reliability.

---

# Workflow Architecture

The extraction process is divided into staged passes to improve efficiency and accuracy.

---

## Stage 1 — Page Rendering

PDF pages are converted into images using **PyMuPDF**.

Two resolution levels are used:

- **Low DPI (triage pass)**  
  Used for fast scanning of document structure.

- **High DPI (extraction pass)**  
  Used only on selected pages for accurate structured extraction.

This staged resolution strategy reduces compute usage and improves performance on large files.

---

## Stage 2 — Triage Pass

Lower-resolution images are analyzed to identify relevant pages.

This step detects:

- Pages likely to contain structured tables  
- Relevant content sections  
- Target data locations  

Irrelevant pages are filtered out before expensive extraction runs.

---

## Stage 3 — Extraction Pass

Relevant pages are processed using a Vision Language Model.

This stage extracts structured candidates including:

- Multi-line table records  
- Numeric values  
- Structured fields  
- Multi-year data entries  

Supports:

- Mixed layouts  
- Wrapped rows  
- Layout variation between pages  

---

## Stage 4 — Validation

Extracted candidates are cleaned and validated.

Validation includes:

- Removing malformed values  
- Filtering corrupted records  
- Deduplicating entries  
- Enforcing structural consistency  

Outputs are normalized into structured formats.

---

## Stage 5 — Page-Level Evidence Tracking

Each extracted record is linked to:

- Source page number  
- Supporting page reference  
- Extraction context  

This improves:

- Traceability  
- Verification workflows  
- Manual auditing reliability  

---

# Key Capabilities

- Processes **multi-hundred-page PDFs**
- Handles **mixed-layout documents**
- Supports **scanned PDFs**
- Extracts **multi-line structured records**
- Produces **structured JSON and CSV outputs**
- Maintains **page-level verification evidence**
- Uses staged processing to reduce compute cost
- Optimizes model usage through multi-resolution workflows

---

# Technical Stack

- Python  
- PyMuPDF  
- Vision Language Models (VLMs)  
- JSON / CSV processing  
- Multi-resolution image workflows  
- OCR-compatible image pipelines  
- OpenAI-compatible API interfaces  
- Qwen 3.5 Vision Models  

---

# Example Output

Typical structured output format:

## JSON Output

```json
{
  "reporting_year": 2024,
  "revenue": 229437.21,
  "scope_1": 7890.61,
  "scope_2": 221546.59,
  "source_page": 111
}
```

## CSV Output

```
year,revenue,scope_1,scope_2,page
2024,229437.21,7890.61,221546.59,111
```

---

# Running the Pipeline

Install dependencies:

```
pip install -r requirements.txt
```

Run extraction:

```
python extract.py
```

---

# Design Philosophy

This workflow was built to address common real-world document challenges:

- Layouts vary across pages  
- Tables wrap across multiple lines  
- OCR output may be inconsistent  
- Documents may contain hundreds of pages  
- Extraction accuracy must be verifiable  

Instead of using a single-pass extraction strategy, this pipeline uses staged processing to improve both performance and reliability.

---

# Known Limitations

- Optimized around structured table extraction workflows  
- Some layouts may require prompt tuning  
- Performance depends on scan quality  
- Currently implemented as a single-script pipeline  
- Designed for experimentation with VLM-based extraction strategies  

---

# Future Improvements

- Modular pipeline structure  
- Configurable prompts  
- Automated validation scoring  
- Extended layout detection logic  
- Performance benchmarking tools  

---

# License

This project is provided for research and experimental workflow development purposes.
