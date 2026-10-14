# Claims file for the Introduction and Related Work (and references)

## 1. Numbers in the text

| Number | Fragment | Source | Label |
|---|---|---|---|
| 2,000 samples; ten partitions | Tangi et al. dataset and runs | seniors-scirep-2025.txt abstract | prior work |
| 70 trips | BMW i3 trips for model validation | docs/dataset-provenance.md (70 trip CSVs); BRIEF | data |
| 100 Hz, 10 ms | controller rate and exchange period | BRIEF; status-report.md section 2 (link 100 times a second) | MEASURED |
| 1 of 16; 0.94% | policy lower in 1 of 16 valid settings, 0.94% more on average | BRIEF canonical numbers | MEASURED |
| 8.28%; 14 of 16; 21.6% | earlier apparent gain, withdrawn; settings; driver aggression 1.5 | docs/week11-plant-correction.md line 145; docs/week10-pil-campaign.md line 173, 209 (21.61%) | earlier campaign, withdrawn |
| 8.05 Wh/km, 5 kW, US06 | controller-free sweep | docs/week11-plant-correction.md line 30 | SIMULATED |
| 0.01% to 0.16% | DP headroom | paper section 04-ems.md; BRIEF | SIMULATED |
| 12 conditions; reviewers dropped | paired statistics noted only by count | docs/paper-table5-stats.json | MEASURED |
| (old row, 8.28% source) | docs/week10-pil-campaign.md line 180; docs/2026-10-07-model-advancement-research.md line 22 | earlier campaign, withdrawn |
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

## 4. Panel items

- R1 (bounded task early): Introduction paragraph 3 states speed fixed by the tracking loop, three actuation numbers, headroom 0.01% to 0.16%, and the bounded claim.
- Contributions rewritten to five items: artefact case and audit checks; headroom bound; corrected comparison with paired statistics over 12 conditions; measured estimation gain and offline-versus-loop finding; on-device costs.
- S2: related work now covers battery-EV versus hybrid headroom, look-ahead RL EMS with HIL (Liu 2017), eco-driving (Sciarretta 2015, Wegener 2021), RL statistical reporting (Agarwal 2021, Henderson 2018), simulator artefacts and specification gaming (Amodei, Skalse, Lehman), sim-to-real (Tobin, Zhao). XGBoost and LSTM cited by chen2016 and hochreiter1997 (entries live in 05-refs.json, per lead).
- "Pre-registered" removed; wording is "acceptance gates and pass criteria were fixed before each experiment". Table caption states the sample is small and chosen for relevance.

## 5. Verification

42 references in 01-refs.json (33 old, 9 new). New entries confirmed by WebSearch: sciarretta2015, liu2017, agarwal2021, amodei2016, skalse2022, lehman2020, tobin2017, zhao2020, wegener2021. All 9 new works were found, but no DOI was resolved for wegener2021 (left blank); Agarwal, Skalse, Tobin pages left blank; Tobin month and Agarwal/Skalse months taken from conference dates, not checked. Lehman author list truncated with "et al.". Liu et al. is described as HIL-checked per its abstract. Only a BEV thermal or cabin-heat energy-management citation could not be confirmed, so none is cited.

## 6. Gaps

- ESP32-S3 datasheet and EPA schedules: as before (no year/version).
- Wegener et al. 2021: whether the vehicle is a battery EV was not confirmed; the text says only "eco-driving in urban scenarios".
- Section 6.1 of the 80-sentence file: Table row for Liu et al. not added (timing statement uncertain).

## 7. Linter and word counts

Before: 1607 prose words, 62 sentences, clean; measure.py n=69, SD 11.6.
After: 1763 prose words, 76 sentences, clean; measure.py n=89, SD 12.2.
Body words: Introduction about 885, Related Work about 860 (excluding table).
