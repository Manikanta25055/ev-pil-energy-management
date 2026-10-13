# Claims file for the Introduction and Related Work (and references)

## 1. Numbers in the text

| Number | Fragment | Source | Label |
|---|---|---|---|
| 2,000 samples; ten partitions | Tangi et al. dataset and runs | seniors-scirep-2025.txt abstract | prior work |
| 70 trips | BMW i3 trips for model validation | docs/dataset-provenance.md (70 trip CSVs); BRIEF | data |
| 100 Hz, 10 ms | controller rate and exchange period | BRIEF; status-report.md section 2 (link 100 times a second) | MEASURED |
| 1 of 16; 0.94% | policy lower in 1 of 16 valid settings, 0.94% more on average | BRIEF canonical numbers | MEASURED |
| 8.28% | earlier apparent gain, withdrawn | docs/week10-pil-campaign.md line 180; docs/2026-10-07-model-advancement-research.md line 22 | earlier campaign, withdrawn |
| 9.44 to 0.24 Wh/km, 10x noise, US06 | Kalman estimator | BRIEF canonical numbers | MEASURED |
| 120 of 120, one clean hour, no false alarm | bias-aware detector | BRIEF canonical numbers | MEASURED |
| 10.4%; 5.1%; 25 m | planner | BRIEF canonical numbers | SIMULATED |
| 87%; 1.2% | linear regression versus Transformer | BRIEF contributions; status-report.md lines 33-35 | MEASURED cost, host-trained accuracy |
| 55 taxis; 0.159 kWh | Zhang et al. | Applied Energy 275:115408 abstract (web) | prior work |
| 30%; four trips | Baluch et al. | abstract (TRID/Southampton record) | prior work |
| about 89% | Wu et al. versus dynamic programming | abstract (IDEAS/BIT record) | prior work |

## 2. Mismatches

- VED year: docs/dataset-provenance.md gives 2020; Crossref gives IEEE TITS vol. 23, no. 4, pp. 3302-3312, April 2022 (early access 2020). The reference entry uses the Crossref data.
- Trip count: status-report.md section 35 says 72 logged trips; dataset-provenance.md lists 70 trip CSVs; the BRIEF says 70. 70 is used.

## 3. Gaps

- ESP32-S3 datasheet: version and year were not fixed (more than two editions exist); entry has no year or version. The lead should add the edition used.
- EPA drive schedules: web resource, no year.
- Pages not confirmed and left blank: Vaswani (5998-6008 is given, confirmed), Kusupati, Lin et al., David et al.
- Seo and Kang (2025) is cited from its title and Crossref record only; its abstract could not be retrieved, so it is not in the positioning table.
- Table cells for Wu, Sun and Xiong data sources are "not stated": abstracts did not name the driving data.
- Haarnoja entry has no DOI; PMLR page used as URL.
- Tangi et al. "next steps" statement is taken from the paper's own limitations and future scope section.

## 4. Verification

32 references in 01-refs.json. DOIs were checked against Crossref (curl) for all entries with a DOI; non-DOI entries (Haarnoja, Vaswani, Kusupati, Lin, David, Malhotra, Bellman, ESP32-S3, EPA) were checked by web search of the proceedings or catalogue page. Pool keys all verified.

## 5. Linter and word counts

prose_lint.py: "1583 prose words, 62 sentences; clean - no machine-writing tells detected".
Introduction: 879 words including heading and bullets. Related Work: 663 words in the four subsections, plus a one-sentence table lead-in and the table.
