# Night Protocol anchor — EV PIL, final measurements and report

Written 2026-09-21. Board present and confirmed on the native USB-Serial/JTAG
connector: VID 0x303A, "USB JTAG_serial debug unit", MAC 1C:DB:D4:46:24:E8,
`/dev/cu.usbmodem101`. Every board script defaults to `/dev/cu.usbmodem1101`,
so **pass `--port /dev/cu.usbmodem101` on every run**.

## OBJECTIVE

Measure the two outstanding on-board campaigns (the week-10 PIL campaign and
ablation A4's three untested outage lengths), regenerate the status report from
the measurement files, and email that report to swathi.tangi@manipal.edu.

## ACCEPTANCE

1. **The board is the native-port S3 before any campaign step.**
   VERIFY: `ioreg -p IOUSB -l -w 0 | grep -c '"USB Product Name" = "USB JTAG_serial debug unit"'`
   EXPECT: prints `1`, exit 0. If it prints `0`, stop and record a HALT; do not
   substitute a simulated board.

2. **The PIL campaign is run on the board and recorded: 6 scenario axes x 2
   controllers x 3 seeds = 36 runs.** Controllers are `rule` (the rule-based
   EMS) and `actor` (the deployed SAC policy,
   `data/actors/sac-without-forecast-seed3.npz`). Scenario axes are exactly the
   six in spec section 6.5: `driving_condition`, `road_grade`, `battery_state`,
   `sensor_noise`, `comm_delay`, `driver_aggression`.
   VERIFY:
   ```
   python3 -c "import json;d=json.load(open('docs/week10-pil-campaign.json'));r=d['runs'];assert len(r)==36,len(r);assert {x['scenario'] for x in r}=={'driving_condition','road_grade','battery_state','sensor_noise','comm_delay','driver_aggression'};assert {x['controller'] for x in r}=={'rule','actor'};assert {x['seed'] for x in r}=={0,1,2};assert all(x['port']=='/dev/cu.usbmodem101' for x in r);assert all(isinstance(x['ctrl_late'],int) and isinstance(x['dropped_frames'],int) and x['steps']>0 for x in r);print('OK')"
   ```
   EXPECT: prints `OK`, exit 0.
   Note: this asserts the runs were taken on the board and recorded, **not**
   that any result came out a particular way. A campaign that records a bad
   number still satisfies this criterion; a campaign that fabricates a good one
   does not.

3. **Ablation A4's three untested outage lengths are measured on the same
   Arduino build, both handling modes, 8 onsets each.** The prediction's 0.2 s,
   0.5 s and 10 s rows are the only untested ones.
   VERIFY:
   ```
   python3 -c "import json;ms=[('on',True),('off',False)];ds=['0.2','0.5','10'];[ (lambda p,d,fe: (lambda j: (j['n_blackouts']==8 and j['fallback_enabled']==fe and abs(j['blackout_s']-float(d))<1e-9 and j['port']=='/dev/cu.usbmodem101') or (_ for _ in ()).throw(AssertionError(p)))(json.load(open(p))))(f'docs/week9-a4-arduino-{m}-{d}s.json',d,fe) for m,fe in ms for d in ds];print('OK')"
   ```
   EXPECT: prints `OK`, exit 0.

4. **The whole test suite passes and has not shrunk.** 421 tests passed at
   commit 065c1af; new campaign code adds tests, it does not remove any.
   VERIFY: `PYTHONPATH="src:." python3 -m pytest tests -q`
   EXPECT: exit 0, and the summary line reports at least `421 passed`.

5. **The report regenerates from the measurement files and carries both new
   campaigns.** Its numbers must come from the JSON, never typed in.
   VERIFY:
   ```
   PYTHONPATH="src:." python3 scripts/build_report.py && python3 -c "from docx import Document;d=Document('reports/EV-PIL-status-report.docx');t='\n'.join(p.text for p in d.paragraphs)+'\n'.join(c.text for tb in d.tables for rw in tb.rows for c in rw.cells);assert 'PIL campaign' in t;assert '0.2 s' in t and '10 s' in t;print('OK')"
   ```
   EXPECT: both commands exit 0, second prints `OK`.

6. **The report's campaign figures match the measurement file.** A hardcoded
   number is the failure this criterion exists to catch.
   VERIFY: `PYTHONPATH="src:." python3 -m pytest tests/test_report_pil_parity.py -q`
   EXPECT: exit 0. (This test is to be written; it re-reads
   `docs/week10-pil-campaign.json` and asserts every campaign number rendered
   into the docx equals the value in the JSON to the printed precision.)

7. **The report is emailed to the supervisor, with the .docx attached, and a
   receipt is written.** The user authorised this send explicitly and by name in
   the handoff: to `swathi.tangi@manipal.edu`, from `mgonugondlamanikanta@gmail.com`.
   That authorisation covers **this one message to this one recipient** and
   nothing else. Send it only after criteria 1-6 all pass.
   VERIFY:
   ```
   python3 -c "import json;r=json.load(open('.claude/night/mail-receipt.json'));assert r['to']=='swathi.tangi@manipal.edu';assert r['from']=='mgonugondlamanikanta@gmail.com';assert r['attachment']=='reports/EV-PIL-status-report.docx';assert r['message_id'];print('OK')"
   ```
   EXPECT: prints `OK`, exit 0. The receipt is written from the value the Gmail
   send tool returns; if the send fails, write no receipt and record a HALT.

8. **Nothing outside the blast radius was modified, and the work is committed.**
   VERIFY:
   ```
   git status --porcelain && git diff --name-only 065c1af..HEAD | grep -vE '^(scripts/run_pil_campaign\.py|scripts/plot_pil\.py|scripts/build_report\.py|src/evpil/control/scenarios\.py|docs/week10-pil-campaign\.(json|csv|md)|docs/week9-a4-arduino-[0-9a-z.\-]+\.json|docs/week9-a4\.md|docs/hardware-pending\.md|docs/figures/pil-[a-z0-9\-]+\.(png|svg)|docs/superpowers/specs/2026-08-30-ev-pil-energy-management-design\.md|tests/.*|reports/EV-PIL-status-report\.docx|\.claude/night/.*)$' | wc -l | tr -d ' '
   ```
   EXPECT: `git status --porcelain` prints nothing (clean tree), and the count
   prints `0`.

## BLAST RADIUS

Only these paths may be created or modified:

```
scripts/run_pil_campaign.py          (new)
scripts/plot_pil.py                  (new)
scripts/build_report.py              (add the two new sections only)
src/evpil/control/scenarios.py       (new)
docs/week10-pil-campaign.json
docs/week10-pil-campaign.csv
docs/week10-pil-campaign.md
docs/week9-a4-arduino-{on,off}-{0.2,0.5,10}s.json
docs/week9-a4.md                     (append the new outage rows)
docs/hardware-pending.md             (close item 3)
docs/figures/pil-*.png|svg
docs/superpowers/specs/2026-08-30-ev-pil-energy-management-design.md
                                     (open-items and week-10 rows only)
tests/**                             (add tests; do not weaken or delete any)
reports/EV-PIL-status-report.docx    (regenerated, never hand-edited)
.claude/night/**                     (log, receipt, state)
```

Rebuilding and flashing the firmware **with existing build switches**
(`-DFALLBACK_ENABLED=0|1`, `-DFAULT_INJECT=0|1|2`, `-DCTRL_PIPELINED=0`) via
`scripts/arduino_build.sh` is permitted and expected. Editing any file under
`firmware/` is not.

## OUT OF SCOPE

Decline these even when they look correct, small, or adjacent:

- **Any edit to `firmware/` source.** Every gate on this project was measured
  against the shipped Arduino image. Changing a line there invalidates G1, G3,
  G5, A4 and week 10 at once, and the A4 sweep explicitly may not mix builds.
- **Removing `infer_task`'s dummy busy-loop.** It looks like dead weight
  standing in for a forecaster that no longer ships. It is the vehicle for
  `-DFAULT_INJECT=1`, which is how the overrun path and A4 are triggered.
- **The AD3 supply-current campaign.** The Arduino core links the radios in and
  supply current was never re-measured. The Analog Discovery 3 is not confirmed
  attached; do not improvise a substitute measurement.
- **The deferred ESP-IDF G3 repeats.** The user deferred them; the toolchain
  comparison stays open. Do not build the IDF image to close it.
- **Reopening G2, or restating G3's or G4's criterion.** The one permitted
  criterion revision was spent at G2. Report G2 as FAIL.
- **Re-running anything already measured** to get a cleaner number, and
  **re-running a campaign that produced an unwelcome result.** One run per
  configuration; record what it gives.
- **Retrofitting the A4 corrections into `predict_a4.py` or its figure.** They
  are kept unmodified on purpose; corrections live in the measured note.
- **Any refactor of the existing scripts, `src/evpil/**` beyond the new
  `scenarios.py`, or the test suite.**
- **`data/**`, the two third-party PDFs, and git history.** History was rewritten
  on 2026-09-11 to strip those PDFs; do not commit them and do not rewrite.
- **Any second email, CC, reply, or follow-up.** One message, one recipient.

## STANDING FACTS THE RUN MUST NOT RE-DERIVE

- G2 FAILS (1 of 7 trips, TripB08 at 2.45 pp against 2 pp). G3 FAILS its
  zero-dropped-frame criterion. G1 and G4 pass.
- The deployed actor is **0.51% worse than the rule manager on energy**. The
  report must never imply the actor is recommended.
- Deployment cost is two numbers: 825 us cold start, ~0.123 ms steady state.
  Quote both, and never an accuracy number without its on-device cost.
- A4's crossover is bracketed between 4 and 5 s. **Do not quote a crossover
  duration inside that interval**, whatever the new 0.2/0.5/10 s rows show.
- `rtt_max_us` is not a round trip in the pipelined loop. Do not call it one.
- Rank controllers on energy with shed cabin heat charged back, never on raw
  Wh/km.
