# Paper brief (read all of this before writing anything)

This folder holds a MOCK manuscript in IEEE Access format, to be shown to the
supervising professor. Seven agents each write one part. A lead assembles the
parts into one Word file. You write only your part, as Markdown, in the format
in section 7. Do not create a Word file.

Repository root: `/Users/manikantagonugondla/Desktop/EV Drives Improvement`
(the path contains spaces; quote it in shell commands).

## 1. Working title

Learned Versus Rule-Based Energy Management for Electric Vehicles on a
Microcontroller: A Processor-in-the-Loop Study With Pre-Registered Acceptance
Gates

## 2. The story the paper tells (every section must fit this)

1. **Where the work starts.** Tangi et al. (Scientific Reports, 2025, cite
   `[@tangi2025]`) predicted electric-vehicle range, optimum acceleration and
   optimum velocity with Random Forest, Extra Trees, Linear Regression and LSTM
   models and their ensembles, on a synthetically generated dataset of 2,000
   samples, and served the models through a web application. That study showed
   that data-driven models can estimate driving parameters. It left three
   things open, and this paper takes up each one:
   - the data were synthetic, so the question of agreement with logged trips
     was open;
   - the models predicted offline and did not close a control loop;
   - nothing ran on an embedded controller under a real-time deadline.
2. **What this work does about each.** (a) Logged data: 70 BMW i3 trips plus
   the Vehicle Energy Dataset, with a longitudinal vehicle model validated
   against them. (b) Closed loop: a forecaster, a rule-based energy manager and
   a Soft Actor-Critic (SAC) policy, all driving the simulated vehicle. (c)
   Embedded real time: everything runs on an ESP32-S3 microcontroller in a
   processor-in-the-loop (PIL) arrangement at 100 Hz, with timing measured.
3. **Method stance.** Acceptance gates and pass criteria were written before
   each experiment. Results that fail a criterion are reported as failures. A
   result is labelled MEASURED (ran on the board) or SIMULATED (host only).
4. **Main finding (negative).** After a vehicle-model fault was found and
   fixed, the learned policy does not beat the rule manager: lower energy in 1
   of 16 board settings, 0.94% more energy on average, and worse speed tracking
   on the aggressive US06 cycle. Giving the policy the forecast changes nothing
   measurable. An apparent 8.28% gain in an earlier campaign came from the
   model fault and is withdrawn in the paper itself.
5. **Where the gain was.** The energy lost under sensor noise sits in the speed
   loop, not the energy manager. A two-state Kalman speed estimator removes it
   (9.44 to 0.24 Wh/km at 10x noise on US06, MEASURED). A bias-aware fault
   detector catches 120 of 120 injected speed-sensor faults with no false alarm
   in one clean hour (MEASURED). Learned reviewers (GRU, FastGRNN) classify
   faults better offline and control the vehicle worse in the loop (SIMULATED).
6. **Outlook, simulated only.** A classical dynamic-programming speed planner
   saves 10.4% on a US06-derived route with no traffic and 5.1% when held
   within 25 m of the recorded drive; a learned student policy saves 0.0%.
7. **Takeaway.** On this class of hardware and this problem, classical
   estimation and hand-written rules were the methods that survived
   measurement. The paper's contribution is the measured comparison and the
   method that exposed the artefact, not a new learned controller.

### Tone toward the earlier work (important)

The earlier study is by the same research group. Describe it accurately and
respectfully as the starting point. State its own declared scope (synthetic
data, offline prediction, web application). Do NOT list faults in it, do not
use words such as "flawed", "leak", "invalid" about it. The safeguards of this
work (trip-level splits, a check that the target cannot be computed from the
inputs, a shuffled-label check, a persistence baseline) are presented as design
requirements of THIS work, in neutral terms.

## 3. Section map and owners

| Id | Heading in the paper | Owner | Words (body) |
|---|---|---|---|
| sec:intro | I. INTRODUCTION | Agent 1 | 750-900 |
| sec:related | II. RELATED WORK | Agent 1 | 650-800 |
| sec:platform | III. EXPERIMENTAL PLATFORM AND METHOD | Agent 2 | 1000-1200 |
| sec:plant | IV. VEHICLE MODEL AND DATA | Agent 3 | 1000-1200 |
| sec:forecast | V. ON-DEVICE POWER FORECASTING | Agent 4 | 1100-1300 |
| sec:ems | VI. ENERGY MANAGEMENT: RULES AGAINST A LEARNED POLICY | Agent 5 | 1300-1500 |
| sec:estimation | VII. SPEED ESTIMATION AND SENSOR-FAULT DETECTION | Agent 6 | 1300-1500 |
| sec:planning | VIII. SPEED PLANNING | Agent 7 | 350-450 |
| sec:discussion | IX. DISCUSSION AND LIMITATIONS | Agent 7 | 600-750 |
| sec:conclusion | X. CONCLUSION | Agent 7 | 200-280 |

Abstract, index terms, acknowledgment and author block are written by the lead.
Do not write them.

You may refer to another section with `Section @sec:id`. Do not describe
another agent's results in detail; one clause and a cross-reference is enough.

## 4. Sources (read what your assignment names, in this order)

- `paper/sources/status-report.md`: the 78-page internal status report as
  text, 37 numbered sections with all tables. Written in plain language for a
  non-specialist; the paper must be rewritten in academic register, never
  copied. It is the map: it tells you which result lives where.
- `docs/*.md`: the weekly records, more precise than the report.
- `docs/*.json`, `docs/*.csv`: the numbers themselves. **Every number in your
  text must come from one of these files or from a `docs/*.md` record.** When
  the report and a JSON file disagree, the JSON wins; note the disagreement in
  your claims file.
- `src/evpil/`, `firmware/main/`, `scripts/`: code, for how something works.
- `paper/sources/seniors-scirep-2025.txt`: the earlier study's text.
- `paper/sources/seniors-btech-report-2024.txt`, `project-plan.txt`: background
  only; do not cite them.
- `docs/dataset-provenance.md`: dataset citations with DOIs.

Internal codes in the sources must NOT appear in the paper. Use these names:

| Internal code | Name in the paper |
|---|---|
| G1 ... G5 | acceptance gates G1 to G5 (these labels are kept; defined in Section III) |
| A1, A2, A3, A4 (ablations) | describe by content: "physics-loss ablation", "distillation and quantisation study", "forecast ablation", "fallback ablation" |
| b0 / shipped loop | baseline speed loop |
| B3, B3a | one-state Kalman filter (mention only if needed) |
| B5 | two-state Kalman speed estimator |
| B6 | acceleration-residual fault detector |
| B7 | bias-aware fault detector |
| B8 | fused fallback estimator |
| rule monitor / rule helper | rule monitor |
| reviewers (GRU, FastGRNN, host GRU) | learned reviewers |
| actor | learned policy (SAC) |
| rule manager / rules | rule-based energy manager |
| "week N" | never mention weeks; describe campaigns by content |
| Jev, Laya, Kev, Nimble, Codex, Claude | never mention |
| "the board", "the chip" | "the microcontroller" or "the target"; name it once as ESP32-S3 |

Canonical headline numbers (use exactly these where they appear; check them
against the JSON and report a mismatch in your claims file instead of silently
changing them):

- Board campaign after the model correction: 36 runs, 2,282,832 control steps,
  0 late steps. Learned policy lower energy in 1 of 16 valid settings, 0.94%
  more on average.
- Simulated retraining: learned policy without forecast 154.86 +- 0.51 Wh/km on
  HWFET against 153.90 for the rules.
- Forecast at 3 s horizon: Transformer 11.029 kW against naive 13.219 kW
  (16.6% better); linear regression 11.308 kW.
- On-target forecaster latency 36.46 ms against a 40 ms budget; first estimate
  22.28 ms. 8-bit quantisation costs 0.95% accuracy, 3.6x smaller.
- Learned policy on target: 0.121 ms, 19.3 KB.
- Loop timing: 59,650 loops in ten minutes, 99.9% within 25 us of slot.
- Plant validation fails on 1 of 7 validation trips (state-of-charge bound
  missed by 0.45 percentage points, 2.45 against 2.00).
- Sensor noise, US06, 10x: baseline loop loses 9.44 Wh/km (190.98 to 200.42);
  two-state Kalman 0.24.
- Bias-aware detector on target: 120 of 120 injected faults within 0.32 s, 0
  false alarms in 1 clean hour, three noise draws.
- Planner (simulated): 10.4% on US06-derived route, 1.2% HWFET; 5.1% within
  25 m corridor, 9.7% within 100 m.

## 5. Honesty rules (these override everything else)

- Never invent a method, a number, a dataset, a result or a reference. If a
  fact you need is not in the sources, write the sentence without it and list
  the gap in your claims file.
- Every result sentence makes clear whether it was measured on the
  microcontroller or simulated on the host. Do not let a simulated number read
  as measured.
- Report failures as failures: gate G2 fails on 1 of 7 trips; gate G3 fails
  its zero-dropped-frame criterion; the acceleration-residual detector is not
  usable; the fused fallback estimator fails for a vehicle 10% heavier on US06;
  the rule monitor's advantage on the target did not repeat.
- The arrangement is processor-in-the-loop, not hardware-in-the-loop: the
  processor is real, the motor, inverter and battery are simulated. Say this.
- Faults were injected in software. No physical accelerometer was used.
- Rank controllers on energy with the shed cabin heat charged back, as the
  sources do ("comparable energy scale"); never on raw Wh/km alone.
- Do not round a number so that a failing result looks like a pass.

## 6. Prose rules

Read `~/.claude/skills/human-academic-prose/SKILL.md` and
`~/.claude/skills/human-academic-prose/reference/wordlists.md` before drafting.

- Third person or passive. No "I", "we", "our", "us". Use "this work", "the
  study", "the authors" sparingly.
- No em dashes and no en dashes used as dashes. Use commas, semicolons or two
  sentences. Number ranges are written "4 to 5 s".
- No evaluative adjectives without a number behind them (robust, novel,
  comprehensive, significant, crucial, seamless, state-of-the-art, promising,
  remarkable). "Significant" is allowed only for a stated statistical test.
- Plain verbs: use, show, allow, need. Not utilize, leverage, showcase,
  underscore, facilitate, delve, encompass, necessitate.
- Vary sentence length on purpose: target a sentence-length standard deviation
  of at least 8.6 words. Mix sentences of 6 to 9 words with ones of 30 or more.
- Do not open paragraphs with Furthermore, Moreover, Additionally, In
  addition, In conclusion. Do not end paragraphs with a sentence that restates
  the paragraph.
- Avoid three-item parallel lists as a habit. Twos and fours are fine.
- Expand each acronym on first use inside your own part (the lead will remove
  repeats): PIL, SAC, SOC, EV, RMSE, UDDS, HWFET, US06, GRU, DP, and so on.
- Units: SI with a space (36.46 ms, 9.44 Wh/km, 100 Hz). Use "us" never; write
  microseconds as `µs`.
- American spelling is NOT required; use British spelling consistently
  (modelled, quantisation, behaviour), matching the project's records.
- No bold or italics for emphasis. No bullet lists except a contributions list
  in the Introduction.
- No footnotes. No URLs in the body.

When your draft is done, run
`python3 ~/.claude/tools/prose_lint.py "paper/sections/<your file>.md"`
and fix every HIGH and MED finding. Re-run until clean, then record the final
linter output in your claims file.

## 7. Output format (strict; a script parses it)

Write to `paper/sections/<NN>-<name>.md` exactly as named in your assignment.

```
# SECTION TITLE IN CAPITALS {#sec:id}

Opening paragraph, plain text.

## Subsection Title in Title Case

Paragraph with a citation [@haarnoja2018] or two [@kalman1960; @vaswani2017],
a figure reference Fig. @fig:pil-energy, a table reference Table @tab:gates,
an equation reference (@eq:long), and a section reference Section @sec:plant.

$$ m \dot{v} = F_{t} - F_{r} - F_{a} - F_{g} $$ {#eq:long}

![fig:pil-energy](paper/figures/fig-pil-energy.png){width=col}
Caption: One or two sentences. State MEASURED or SIMULATED in plain words.

Table: tab:gates | Caption text, one sentence. | width=col
| Gate | Question | Criterion | Result |
|---|---|---|---|
| G1 | ... | ... | ... |
```

Rules:
- One `#` heading per section, `##` for subsections, `###` at most one level
  further. No numbering in headings; the script numbers them.
- Inline maths: `$v$`, `$P_{b}$`, `$\eta$`. Keep it to single symbols with
  optional subscript. Display equations use LaTeX inside `$$ ... $$` on one
  line, followed by `{#eq:id}`. Use only common LaTeX (frac, dot, hat, sum,
  Greek, sub and superscripts, `\text{}`); no environments, no `\begin`.
- `width=col` is one column (3.5 in). `width=page` spans both columns (7.16
  in); use it only for a wide table or a figure with several panels.
- A figure line is immediately followed by its `Caption:` line. Each figure
  and table is referenced in the text before it appears.
- Tables: at most 7 columns for `width=page`, 4 for `width=col`; short cell
  text; no merged cells. Numbers carry units in the header.
- Ids are lowercase with hyphens, prefixed `fig:`, `tab:`, `eq:`, and must be
  unique to you: start each id with your section's word, for example
  `fig:ems-...`, `tab:plant-...`, `eq:forecast-...`.

## 8. Figures

You make the figures for your own part, with matplotlib, saved to
`paper/figures/`. Budget is in your assignment.

- Start every figure script with:
  ```python
  import sys; sys.path.insert(0, "paper")
  import figstyle as fs
  fig, ax = fs.figure("col")          # or fs.figure("page", nrows=1, ncols=2)
  ...
  fs.save(fig, "fig-ems-energy")      # writes paper/figures/fig-ems-energy.png
  ```
  Save your script as `paper/figures/make_<same name>.py` and run it from the
  repository root. Read `paper/figstyle.py` first; use its colours `fs.C` and
  hatches, in that order.
- Plot from the JSON and CSV files in `docs/`, never from numbers typed in by
  hand. The existing `scripts/plot_*.py` show how each file is read; do not
  edit or run those scripts, and do not reuse the old PNGs in `docs/figures/`.
- No title inside the figure. Axis labels with units. Legend inside the axes
  where it does not cover data. All text at least 8 pt at final size (figstyle
  sets this; do not shrink fonts).
- Figures must be readable in greyscale: separate series by marker, line style
  or hatch as well as colour.
- After saving, open the PNG with the Read tool and check it: no overlapping
  labels, no clipped text, nothing unreadable. Fix and re-check.

## 9. References

Cite with keys. The pool below is shared; Agent 1 writes the full entries for
every pool key. You may use any pool key without writing its entry.

| Key | Work |
|---|---|
| tangi2025 | Tangi, Vatsa, Opam, Bonthagorla, Gaonkar, "Smart strategies for improving electric vehicle battery performance and efficiency," Scientific Reports, 2025, doi 10.1038/s41598-025-25987-1 |
| i3data | BMW i3 trip dataset, IEEE DataPort, doi 10.21227/6jr9-5235 (details in docs/dataset-provenance.md) |
| ved | Vehicle Energy Dataset, IEEE Trans. Intelligent Transportation Systems, doi 10.1109/TITS.2020.3035596 |
| haarnoja2018 | Soft Actor-Critic (Haarnoja et al., ICML 2018) |
| kalman1960 | Kalman, "A new approach to linear filtering and prediction problems," 1960 |
| vaswani2017 | "Attention is all you need," NeurIPS 2017 |
| cho2014 | GRU (Cho et al., EMNLP 2014) |
| kusupati2018 | FastGRNN (Kusupati et al., NeurIPS 2018) |
| raissi2019 | Physics-informed neural networks (Raissi, Perdikaris, Karniadakis, J. Comput. Phys. 2019) |
| hinton2015 | Knowledge distillation (Hinton, Vinyals, Dean, 2015) |
| jacob2018 | Integer-only quantisation (Jacob et al., CVPR 2018) |
| bellman1957 | Dynamic programming (Bellman, 1957) |
| esp32s3 | Espressif ESP32-S3 Series Datasheet |
| epacycles | U.S. EPA dynamometer drive schedules (UDDS, HWFET, US06) |

To cite anything else, you must (1) confirm with WebSearch that the work
exists with exactly those authors, title, venue and year, (2) add it to
`paper/sections/<NN>-refs.json` as a list of objects with fields `key`,
`authors` (list of "F. M. Surname"), `title`, `venue`, `volume`, `number`,
`pages`, `month`, `year`, `doi`, `verified_url`. Leave a field as "" when it
does not apply. A reference you could not verify is not cited.

## 10. Claims file (required)

Write `paper/sections/<NN>-claims.md` with:

1. A table: every number in your text | the sentence fragment | source file
   and key or line | MEASURED or SIMULATED.
2. "Mismatches": any place the report, a record and a JSON file disagree.
3. "Gaps": facts you wanted and could not find.
4. The final `prose_lint.py` output, and the word count of your section.

## 11. Hard limits

- Write only inside `paper/sections/` and `paper/figures/`. Do not edit any
  other file in the repository, including `paper/BRIEF.md` and
  `paper/figstyle.py`.
- No git commands that change anything (no add, commit, checkout, stash).
- Do not flash, reset or talk to any board or serial port. Do not run
  `scripts/run_*.py`, `scripts/train_*.py`, `pytest`, or any simulation. You
  only read result files and plot them.
- Do not install packages.
- The machine has 8 GB of memory and other agents are working at the same
  time: no multiprocessing, load one data file at a time.
- Your final message to the lead: the files you wrote, the word count, the
  linter result, and the mismatches and gaps, in under 200 words.
