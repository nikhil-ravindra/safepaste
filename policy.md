# Company policy (plain English) — owner: Person 2
# Data Protection & Masking Policy Guidelines

This document outlines the operational rules and placeholder mapping standards used by SafePaste to sanitize sensitive operational data before transmission to cloud LLM providers.

## Masking & Mapping Rules

When sensitive entities are detected within incoming prompts or documents, SafePaste replaces them with deterministic placeholders using the `⟦CATEGORY_INDEX⟧` format.

| Category | Description & Pattern Examples | Placeholder Structure | Example Source Text | Example Masked Output |
| :--- | :--- | :--- | :--- | :--- |
| **Client Name** | Registered corporate entities, trade names | `⟦CLIENT_N⟧` | *Aarav Logistics Pvt Ltd* | `⟦CLIENT_1⟧` |
| **Financial Amount** | Currency figures (INR ₹ values, decimals) | `⟦AMOUNT_N⟧` | *₹14,50,000* | `⟦AMOUNT_1⟧` |
| **API Keys / Secrets** | High-entropy secrets, bearer tokens, test/live keys | `⟦API_KEY_N⟧` | *ak_live_89f2a41b* | `⟦API_KEY_1⟧` |
| **Project Codenames** | Internal project identifiers | `⟦PROJECT_N⟧` | *Project Trishul* | `⟦PROJECT_1⟧` |
| **Purchase Orders** | Procurement order reference numbers | `⟦PO_N⟧` | *PO-2026-8891* | `⟦PO_1⟧` |
| **Documents / Batches**| Invoices, batch references, legal docs | `⟦DOC_N⟧` / `⟦BATCH_N⟧` | *Batch #9910* | `⟦BATCH_1⟧` |

## Data Sanitization Workflow

1. **Detection**: Input text is processed through regex patterns and locally hosted inspection models.
2. **Replacement**: Detected sensitive strings are assigned indexed placeholders (`⟦...⟧`) in sequential order.
3. **Audit Log**: Source-to-placeholder mappings are stored solely in ephemeral local memory (`mask.py` / `audit_log.py`).
4. **Cloud Execution**: Sanitized prompts are dispatched to external endpoints (`cloud.py`).
5. **Reconstruction**: Responses returning from the cloud are restored back to original values before rendering to the user interface.
