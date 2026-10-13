# Claims, Section IV (03-plant.md)

| Number | Fragment | Source | Status |
|---|---|---|---|
| 70 trips; 0.1 s | archive of 70 trips, every 0.1 s | docs/dataset-provenance.md (observed sample interval) | data |
| 33 eligible; -3.3 to 10.2 C | 33 passed; winter envelope | dataset-provenance.md, trip eligibility | data |
| 19/7/7 | split by trip | data/splits.json (train 19, val 7, test 7, n_eligible 33) | data |
| 504 VED trips, 3 Leafs, 443 eligible | VED subset | dataset-provenance.md; docs/ved-eligibility.csv | data |
| UDDS 1369 s 11.99 km; HWFET 765 s 16.51 km; US06 600 s 12.89 km | cycles | dataset-provenance.md lines 550-552 | data |
| 543 W, 127.3 W/C, 21 C | auxiliary load | data/i3_params.json aux | data |
| 50 kW regen ceiling (assumed) | regen | i3_params.json citations.regen | data |
| 1270 kg, 2.38 m2, 0.3498 m, 9.665, 250 Nm, 125 kW, 0.95 | Table params | i3_params.json published, citations | data |
| 0.01947, 0.2202, 0.1706, 0.010 ohm | identified | i3_params.json identified | data |
| 61.7 Ah | Coulomb counting | docs/g2-plant-validation.md | data |
| 27.4%, 48.6%; 7.0%, 8.3%; 0.19 pp | G2 parts A, B, C | docs/g2-plant-validation.md result block; g2-per-trip.csv | SIMULATED vs logged |
| 2.45 vs 2.00 pp; 1.86, 1.76 pp | B08 miss | g2-per-trip.csv soc_abs_error | SIMULATED vs logged |
| -0.85 | torque spread vs relative error | g2-plant-validation.md | data |
| 10.4%, 13.6%, -21% to +30% | B08 bias, spread | g2-plant-validation.md "What is still wrong" (13.6% is the bias in mechanical energy) | data |
| 0.01947 vs 0.00878, 2.2 | coastdown ratio | g2-plant-validation.md; ved-generalisation.md | data |
| 89 trips; 16.9/14.4/13.4%; 55/64/67; 3.5 and 2.5 points | VED arms | docs/ved-generalisation.csv/.md | SIMULATED vs logged |
| 77.7%; -15.8%, +15.6% | floor, temperature slope (arm C) | ved-generalisation.md | SIMULATED vs logged |
| 5 kW: 8.05 vs 156.16 Wh/km, 12.888 vs 4.453 km, 0.0013 vs 16.15 m/s; 190.39; 40 kW 174.85 vs 189.80 | fault table | docs/week11-plant-correction.json | SIMULATED |
| 40 to 125 kW | ceiling range | docs/week11-plant-correction.md | design range |
| +0.07% (-0.03 to +0.17), 0.46%, 0.57%, 16 cells | rule-arm check | docs/week11-rule-arm-check.json | MEASURED |

## Mismatches
- Brief says "70 BMW i3 trips"; only 33 passed eligibility, and the split covers those 33. The text says so.
- The "1 of 7 trips" is by SOC part C only; parts A and B pass on all seven.
- Status report says 89 Leaf trips "held-out"; the ved-generalisation record says the 89 test trips stay sealed. The text says "held-out" only.

## Gaps
- The coastdown reference for 0.00878 (INL/DOE report [L1] in the repo) is not in the shared pool; the text cites it without a key.
- The second wrong explanation (policy used the ceiling, rules did not; both used 40 to 125 kW) comes from the project memory note, not a docs file. docs/week10-pil-campaign.md says only that the ceiling was not logged. Check before submission.
- VED eligibility rule details not given in the text.
- "Rule ceiling rarely binds" is from week11 docs (ceiling near 125 kW), not quantified.
- The Section III cross-reference for gate definitions is assumed; the text defines G2 fully.

## Linter and word count
prose_lint.py: 1422 prose words, 57 sentences, "clean - no machine-writing tells detected".
Body word count about 1270 including headings and inline symbols; about 1200 excluding them (captions, equations and table excluded).
