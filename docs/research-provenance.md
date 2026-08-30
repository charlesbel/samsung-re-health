# Research Provenance & Methodology

## Scientific & Reverse Engineering Methodology

`samsung-health-cloud` reconstructs the private cloud synchronization protocol and field definitions of Samsung Health using a disciplined, multi-layered provenance framework.

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

### Bundled Baseline Catalog & Non-Personal Guarantee

The runtime baseline catalog bundled in `src/samsung_health_cloud/resources/manifests.json` contains strictly non-personal, account-independent manifest IDs and schema revision numbers:
- All push IDs are strictly empty strings (`"push_id": ""`), ensuring no device or account routing tokens are packaged.
- Revisions reflect the baseline schemas at release time. As Samsung Cloud updates data schemas over time, revisions in the bundled baseline may become superseded. When online synchronization is run (`samsung-health sync`), the client automatically discovers and updates local manifests with active cloud revisions.

### Attribution and Independent Verification

All field definitions in `samsung_health_cloud/semantics.py` explicitly declare their provenance tag, reference source, and caveats. Structural coverage of fields is tracked independently from semantic interpretation to guarantee full data fidelity.
