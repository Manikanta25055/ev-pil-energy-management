# Claims, Section IV (03-plant.md), round 2

## Panel items
- R7 (plant fidelity): paragraph pair in "Limits of Plant Fidelity". Lists the rolling coefficient at 2.2 times a published coastdown value, the rotational factor 0.1706, the 50 kW regeneration ceiling, drivetrain efficiency 0.95, R0 at its lower bound, the winter-only envelope, the campaigns at 12 C, G2 failing on 1 of 7 trips, and 13.4% to 16.9% median energy error on transfer. States that this threatens absolute Wh/km, that a paired ranking is protected only against errors acting on both arms alike, and reports the H3 one-at-a-time sensitivity sweep (update 2b) with its limits.
- Artefact as centre (REFRAME 2.1, 2.2): subsections "The Earlier Campaign and the Apparent Gain", "The Mechanism" (Fig. plant-correction, controller-free sweep), "How It Was Found", "The Fix and Its Consequences", "Checks the Case Implies" (Table plant-checks, the three checks a, b, c). Section retitled; id unchanged. New Fig. plant-reversal (earlier against corrected campaign per setting).
- How it was found: stated plainly that G2 never exercised the ceiling path and could not have failed on it; the cue was three anomalies in the campaign tables; two recorded explanations were wrong; the audit began from a result favouring the learner and no symmetric audit was run (DA M5).
- Repeat campaign: shown to have reproduced the artefact (14 of 16, 8.29%), so reproducibility did not guard against a plant fault.
- Pointer for W4: 04-ems.md can point to this section for the full account.

## Numbers
| Number | Fragment | Source | Status |
|---|---|---|---|
| 70 trips; 0.1 s; 33 eligible; -3.3 to 10.2 C; 19/7/7 | data | docs/dataset-provenance.md; data/splits.json | data |
| UDDS 1369 s 11.99 km; HWFET 765 s 16.51 km; US06 600 s 12.89 km | cycles | dataset-provenance.md | data |
| 543 W, 127.3 W/C, 21 C, 50 kW, Table params | model | data/i3_params.json | data |
| 27.4/48.6%, 7.0/8.3%, 0.19 pp, 2.45 vs 2.00 pp | G2 | docs/g2-plant-validation.md; g2-per-trip.csv | SIMULATED vs logged |
| 89 trips; 16.9, 14.4, 13.4% | VED arms | docs/ved-generalisation.csv | SIMULATED vs logged |
| 0.01947 vs 0.00878, 2.2; 0.2202; 0.1706 | coefficients | i3_params.json; g2-plant-validation.md | data |
| 36 runs, 32 valid; 14 of 16; 8.28%; 21.6% | earlier campaign | docs/week10-pil-campaign.json (recomputed: -8.28%, 14 negative); week10-pil-campaign.md 6.2 | MEASURED |
| 7.57/14.54/21.61; 4.79/7.53/10.14; +0.27 UDDS, +0.09 HWFET | demand pattern | week10-pil-campaign.md 6.2, 6.4 | MEASURED |
| 14 of 16; 8.29%; 72.0 kW vs 123.4 kW mean ceiling | repeat campaign | docs/week10-pil-campaign-repeat.json (recomputed over 16 valid settings, diag_delta.p_limit_mean_w) | MEASURED |
| 8.05, 190.39, 12.888 km, 0.0013 m/s; 174.85; 176.71 | before-fix sweep, deployed policy | docs/week11-plant-correction.json | SIMULATED |
| 176.53 | learned, US06 mixed, earlier campaign | week10-pil-campaign.json | MEASURED |
| 156.16, 4.453 km, 16.15; 189.80; 190.71 vs 190.47; 0.48 m/s | after-fix | week11-plant-correction.json | SIMULATED |
| 7% below the optimum (176.7 vs 190.39) | cue | week11-plant-correction.md section 2 | SIMULATED |
| 15 days | first campaign 2026-09-21; fix commit 82ca2fe 2026-10-06 | week10-pil-campaign.md; git log | record |
| "Two limits that never bind give bit-identical outputs" | lead's wording, kept | lead update | record |
| four unit tests, one cycle-level test | fix tests | tests/plant/test_plant.py (4 new); tests/control/test_sim.py (1, commit 0bdab2b) | record |
| +0.07% [-0.03, +0.17], 0.46%, 0.57% | rule-arm check | docs/week11-rule-arm-check.json | MEASURED |
| 190.47 to 150.09; 153.90 to 112.34; 14 of 14 higher; +0.12% to +0.81%; nominal +0.36% US06, +0.20% HWFET | sensitivity sweep | docs/2026-10-14-plant-sensitivity.json | SIMULATED |
| 12 C ambient | campaign ambient | scripts/run_pil_campaign.py T_AMBIENT_C | design |
| 40 to 125 kW range | ceiling range | week10 repeat firmware log; week11-plant-correction.md | MEASURED |

## Mismatches
- Brief: "70 trips"; only 33 passed eligibility. The text says so.
- "1 of 7 trips" is by SOC Part C only; Parts A and B pass on all seven.
- The ceiling means (72.0 and 123.4 kW) are my recomputation over the 16 valid settings of the repeat file; the repeat commit message gives 123 and 72 over all runs. They agree.
- The deployed policy's earlier-campaign US06 figure is 176.53 (week10-pil-campaign.json); the correction note quotes 176.4 (repeat-campaign mean). The text uses the first-campaign cell.
- The 8.28% and 14 of 16 were recomputed from the JSON on the comparable scale and match the record.

## Gaps
- The record does not say who first questioned the anomalies or in what order checks were run; the text gives only the three cues in the correction note.
- Rotational factor 0.1706 is called lumped, not compared with a published value; none was found in the sources.
- Sensitivity sweep limits stated: one policy seed, no noise, one parameter at a time, four parameters only.
- The DP optimum is stated to be computed on the same model with the ceiling open; the week 7 DP action space is not re-read here.
- The "inl2013leaf" key comes from 01-refs.json (confirm it stays).
- Whether five of the 16 settings repeat the nominal condition is from paper-table5-stats.json (REFRAME section 4).

## Lint and measure
Before (old file): prose_lint 1466 words, 55 sentences, clean; sentence-length SD 9.3 (n 61, mean 21.1).
After: prose_lint 1845 words (counts captions and tables), 75 sentences, clean; SD 9.4 (n 83, mean 19.4). Body prose about 1600 words by my count, excluding headings, equations, tables and captions.
