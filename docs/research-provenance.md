# Research Provenance & Methodology

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd.

## Scientific & Reverse Engineering Methodology

`samsung-re-health` reconstructs the private cloud synchronization protocol and field definitions of Samsung Health using a disciplined, multi-layered provenance framework.

### Evidence Hierarchy

1. **Official Documentation (`official_documentation`)**:
   - Primary reference from Samsung Health Data SDK documentation and developer portals.
   - Covers official field names, units, valid numerical ranges, and enumeration mappings for common measurement types (sleep, heart rate, oxygen saturation, exercise, step trends).
2. **Official Schema Conventions (`official_schema_convention`)**:
   - Standard field names defined across public Samsung health data models (such as `start_time`, `end_time`, `time_offset`, `binning_data`) when found within private manifest schemas whose complete hierarchy is not publicly documented.
3. **Decompiled APK Analysis (`apk_decompiled`)**:
   - Reconstructed logic from static inspection of official Samsung Health Android client packages (`com.sec.android.app.shealth`).
   - Only accepted when unambiguous call sites or unit calculations (e.g., multiplier formulas, percentage normalizations) exist in decompiled sources.
4. **Raw Observed Data (`raw_observed`)**:
   - Unverified fields present in cloud synchronization payloads.
   - Kept in their exact raw field names with neutral descriptive statistics (count, min, max, mean, presence) without inferring clinical semantics.

Open-source projects may corroborate a field interpretation but do not outrank Samsung documentation. When the runtime registry uses `open_source`, it denotes that narrower source class rather than an official definition.

### Bundled Baseline Catalog Contents

The runtime baseline catalog bundled in `src/samsung_health_cloud/resources/manifests.json` contains manifest identifiers and schema revisions but no health records or populated routing token:
- All push IDs are strictly empty strings (`"push_id": ""`), ensuring no device or account routing tokens are packaged.
- Revisions reflect the baseline schemas at release time. As Samsung Cloud updates data schemas over time, revisions in the bundled baseline may become superseded. When online synchronization is run (`samsung-re-health sync`), the client automatically discovers and updates local manifests with active cloud revisions.

### Attribution and Independent Verification

Registered field definitions in `samsung_health_cloud/semantics.py` declare a provenance tag and source; uncertain evidence classes also carry explicit caveats. Structural coverage is tracked separately so decoded fields observed in the counted mirror scope are not silently hidden. This does not guarantee complete cloud access, lossless decoding, attachment/E2EE availability, semantic completeness or end-to-end data fidelity.
