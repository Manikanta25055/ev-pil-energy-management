Physics-Informed Transformer and Reinforcement Learning for Real-Time Energy-Efficient Control of Electric Vehicles on an ESP32-S3

Project status report

Manikanta Gonugondla   |   9 October 2026

Phase 1 and Phase 2 complete. Four of five gates measured and passed. Every number in this report comes from a run that can be repeated with one command.


# 1. Summary

The project builds an energy-management controller for an electric car and runs it on a real ESP32-S3 microcontroller. The car itself is simulated in Python. The microcontroller and the simulation talk to each other over a serial cable in real time, so the controller has to meet real deadlines on real silicon rather than in a notebook.

Current correction: the week-10 energy-gain claim is withdrawn because a vehicle-model power ceiling reduced the energy billed without reducing delivered torque. Section 28 separates the original evidence, the fix, and new measurements.

Corrected-model retraining on validation: the no-forecast learned arm averages 154.86 watt-hours per kilometre against 153.90 for the rules. SIMULATED. The corrected board campaign is complete and tabulated in the correction section. The corrected A4 sweep is complete.

The work so far has produced a validated vehicle model, a forecasting model that beats every baseline we could find, measured evidence that it fits inside the microcontroller's compute budget, and a controller that meets its deadlines and survives having its parts broken on purpose. It has also produced several results that went against expectation, and those are reported here as plainly as the successes, because each one changes what the paper can claim.


## Where the gates stand

| Gate | Due | Question it asks | Result |
|---|---|---|---|
| G1 | Week 1 | Is the chip fast enough for a Transformer? | PASS, 6.1x margin |
| G2 | Week 2 | Does the vehicle model reproduce real trips? | FAILS on 1 of 7. Parts A and B pass on every trip; one trip misses the state-of-charge bound by 0.45 of a point. Phase 2 proceeded with the miss recorded, not with the bound relaxed |
| G3 | Week 3 | Does the 10 ms loop close on hardware? | Timing passes by 40x; 3 host stalls in 59,650 loops fail the zero-drop rule. Re-measured in week 7 on the changed firmware |
| G4 | Week 4 | Does any model beat the naive baseline by 10%? | PASS, all four models |
| G5 | Week 6 | Does the forecaster run on the chip in 40 ms? | 36.46 ms measured, fits at 91% |


## The headline numbers

Forecasting three seconds ahead, the Transformer reaches 11.029 kW of error against a naive baseline's 13.219 kW. That is a 16.6% improvement.

It needs 22.28 ms of the 40 ms allowed on one processor core, and 17.9 KB of the 300 KB allowed. It fits.

A plain linear regression reaches 11.308 kW, which is 87% of the same benefit for 1.2% of the computing cost. That comparison is a result in its own right.

Shrinking the model to 8-bit numbers costs 0.95% of accuracy and makes it 3.6 times smaller.

Timed on the chip itself, one prediction takes 36.46 milliseconds against the 40 allowed. The estimate from the week-one compute budget was 22.28, so it was 64% low, and section 13 explains why that gap is a useful result rather than a problem.

The learned controller, trained five times over, finishes at 154.92 watt-hours per kilometre against the conventional controller's 153.90, once the cabin heating it switched off is charged back at what it saved. On that cycle it is reliably slightly worse, which is what week 7's offline optimum predicted. Section 21. The processor-in-the-loop campaign in section 26 appeared to find the opposite on the aggressive cycle. That finding is withdrawn: it came from a fault in the vehicle model, described in section 28.

Removing the forecast from what the controller can see changes nothing measurable: +0.240 watt-hours per kilometre with an interval that contains zero.

The learned controller runs on the chip in 0.121 milliseconds of the 40 allowed and 19.3 KB of the 300, and its answers match the Python original to 2e-06.

On hardware, 59,650 control loops ran over ten minutes with 99.9% of them inside 25 microseconds of their slot, against a limit of 1000. The link lost nothing.

Gate G3 still fails, on 3 occasions where the laptop did not answer in time. The count of loops that missed their own deadline, measured for the first time this week, is 0. Section 15 explains why that distinction matters.

The last experiment of week 9, which switches the failure handling off to measure what it is worth, has been run on the board. It was predicted beforehand to point the opposite way from the obvious reading, and it does: switching the handling off makes typical tracking better, 0.125 against 0.292 metres per second at a one-second outage. The handling is a safety mechanism, and it is not there to improve tracking. Sections 19 and 20.

The same prediction was wrong about how large that gap would be, expecting a factor of twelve where the board shows a factor of 2.3, and wrong that the two versions could not be told apart by the current drawn from the battery. Both corrections are recorded in section 20 rather than folded back into the prediction.

At a five-second outage the handling earns its keep, which is the case it exists for and the one the prediction called best: the worst of eight outages costs 7.39 metres per second with the handling in against 7.95 with it removed, predicted 6.88 against 8.02. The handling is not there because it tracks well; it is there because it fails small where holding on to a stale command fails large. Section 20.


## Week 13 in brief

Week 13, measured on the board: a new speed-sensor fault checker caught all 40 injected faults within 0.32 seconds with no false alarm and no late control step. The earlier checker caught 33 and raised 162 false alarms on one clean drive. Section 30.

Week 13, simulated: small AI helpers judged sensor faults better than hand-written rules and drove the car worse. The rules are kept. Jev was not purchased and is not tested. Section 31.

Week 13, simulated, a new task: letting the car plan its own speed on an empty road saved 10.4% of energy on the aggressive route and 1.2% on the highway route. Section 32.


## Week 14 in brief

Week 14, measured on the board: repeated with two more draws of noise, the new fault checker caught 120 of 120 injected faults with no false alarm in 1 clean hour. The rule helper's small advantage from the first run did not repeat. Section 33.

Week 14, simulated: a backup speed that does not drift cut the largest speed error during a fault from 3.74 to 0.62 metres per second on the highway cycle. It fails for a car heavier than its model in aggressive driving.

Week 14, simulated: with traffic, held within 25 metres of the recorded drive, speed planning still saves 5.1% on the aggressive route.


## The state of the hardware for this report

The development board was attached when this report was generated, and the last outstanding experiment of week 9 was run on it. Section 20 is that measurement. Section 19 is the prediction that was written before it and is kept unchanged, so the two can be read against each other; it says on its heading, its opening paragraph, its figure caption and its table that it is a prediction. Everything else described as measured was measured on the board in earlier weeks and is unchanged.


# 2. What the project is, in plain terms

An electric car wastes energy in ways a driver cannot see. How hard the motor pushes, how much braking energy is recovered, and how much the heater draws all change how far the car goes on a charge. A controller that could see a few seconds into the future could make better choices about all three.

Building that controller raises a question the research literature usually avoids. Models that predict well are large, and cars carry small, cheap processors. A model that works in a laboratory notebook may be far too slow for the hardware it is meant to run on. This project measures that gap instead of assuming it away.


## The four parts of the system

| Part | What it does | Where it runs |
|---|---|---|
| Vehicle model | Simulates the car: motion, motor, battery, road slope, heater, regenerative braking | Python, on the laptop |
| Forecaster | Predicts battery power for the next three seconds | Trained in Python, deployed on the chip |
| Controller | A fast safety loop plus a slower optimising loop | ESP32-S3 |
| Link | Carries state and commands between the two, 100 times a second | USB cable |

The correct name for this arrangement is processor-in-the-loop, not hardware-in-the-loop. The processor is real; the motor, inverter and battery are not. The report says so wherever the distinction matters, because a reviewer who spots an overstated claim will discount everything around it.


## Why the earlier version had to be rebuilt

An earlier project on this topic reported strong accuracy figures. Reading its data-generation code showed the figures could not mean what they appeared to mean. Eight specific faults were found. Three of them matter enough to explain here.

The thing being predicted was calculated from the same numbers fed in as inputs. The model was solving an equation it had already been given, so high accuracy proved nothing.

Training and testing data were split row by row on a continuous recording. Rows one tenth of a second apart are nearly identical, so the model was tested on data it had effectively already seen.

The sequence model was given data reshaped so that it had no time dimension at all. It was then reported as performing badly, which is what any sequence model would do without a sequence.

Each fault has a specific countermeasure in the current design, and each countermeasure is checked by an automated test rather than by intention. The last of the three is re-run correctly in this report, so the comparison against the earlier work is direct.


# 3. The words you need

Everything below recurs through the rest of the report. Nothing after this point assumes you have met any of these terms before.


## The car and the journey

Drive cycle — A standard speed-against-time profile that regulators use to test cars, so that two vehicles are compared on identical journeys. UDDS is stop-start city traffic, HWFET is steady highway, US06 is deliberately aggressive, and WLTC is the modern European standard. They are published second by second.

Regenerative braking — Running the motor backwards as a generator when slowing down, so that braking energy returns to the battery instead of becoming heat in the brake pads. It is the single largest energy lever on an electric car, and this project measures it as worth between 5 and 23 percent.

State of charge — How full the battery is, as a fraction from 0 to 1. Errors in it are quoted in percentage points: being at 62 percent when you should be at 64 is a 2 percentage point error.

Watt-hours per kilometre — How much energy the car uses to travel a kilometre. Lower is better. This vehicle sits around 150 to 190 depending on the cycle and the weather.


## Judging a prediction

RMSE — Root-mean-square error: the typical size of the gap between a prediction and reality, in the same units as the thing predicted. Large mistakes count much more heavily than small ones. Zero is perfect and lower is better.

R-squared — The fraction of the real variation a model explains. One is perfect, zero means the model is no better than always guessing the average, and a negative value means it is worse than guessing the average.

Horizon — How far ahead a forecast reaches. Here it is three seconds, checked at every tenth-of-a-second step along the way. Predicting a tenth of a second ahead is nearly free; three seconds is not.

Persistence baseline — The naive forecast: whatever the power is now, it will still be that in three seconds. It sounds trivial and is famously hard to beat over short horizons, so any model that cannot beat it is worthless. That is why it is a mandatory comparison.

Held-out and sealed data — Data the models are never allowed to see while being built. Seven validation trips are used for tuning. The test trips and the US06 cycle have not been opened at all and will be touched once, at the very end.

Confidence interval — A range expressing how sure a result is. If the interval around a difference includes zero, the honest reading is that the difference cannot be told apart from no difference at all.

Seed — Machine learning that involves randomness gives a different answer each time it is run. Reporting one run is not evidence, so this project trains five per arm and reports the spread.

Ablation — Deliberately removing one component to find out whether it was doing anything. Ablation A1 removes the physics from the training; A3 removes the forecast from the controller.


## The models

Ridge regression — About the simplest useful model there is, a weighted sum of the inputs fitted by solving one equation. 257 numbers. It is in this project as a floor: if an elaborate model cannot beat it, the elaboration bought nothing.

LSTM and Transformer — Two kinds of neural network built for sequences. An LSTM reads the past one step at a time; a Transformer looks at all of it at once. The Transformer is the candidate model this project set out to test.

Reinforcement learning and SAC — Training a controller by letting it drive the simulation many times over and rewarding good outcomes. SAC, Soft Actor-Critic, is a specific and well-regarded algorithm for continuous controls. This is the AI controller under test.

Dynamic programming — An offline method that finds the genuinely best possible sequence of decisions by working backwards from the end of the journey. Far too slow to run in a car, which is fine: its only job is to say what the best score was, so that a real controller can be measured against it.


## The chip

int8 and quantisation — Shrinking a model by storing every number as an 8-bit integer instead of a 32-bit decimal. Four times smaller and faster, at the cost of a little accuracy. Essential on a chip this size.

MAC — Multiply-accumulate: one multiplication plus one addition, the basic unit of work in a neural network. Counting them is the standard way to estimate whether a model will fit a time budget, imperfectly, as this project found twice and in opposite directions.

Deadline and jitter — The control loop must complete every 10 milliseconds. Jitter is how far the actual gap between loops wanders from that figure. The gate allows 1000 microseconds of wander and the chip achieves 25.

Watchdog — A hardware timer that resets the chip if the software stops feeding it. The last line of defence against a controller that has silently hung.

PID controller — The standard workhorse of control engineering. It combines the error now, the error accumulated so far, and how fast the error is changing. A cruise control is a PID.

Feedforward — Working out most of the answer in advance from physics, so the feedback loop only has to correct what is left over. Here it means computing the force needed to follow the target speed, leaving the PID to fix only what the physics got wrong.


# 4. How to read the charts in this report

Every figure in this report has more than one panel, and each panel is explained individually where it appears. The chart types themselves are standard, and this is all that is needed to read them.

Parity plot — Predicted value on one axis, real value on the other, with a diagonal line. A perfect model puts every point exactly on the diagonal. Fuzz around the line is noise. A systematic bend away from it means the model is wrong in a particular operating region, which is far more serious than fuzz.

Histogram — Bars counting how many times a measurement fell into each range. Used here for loop timing: how many of the 59,650 control cycles landed within 25 microseconds of perfect, how many within 50, and so on.

Cumulative curve — Instead of how many landed in each band, it answers what percentage landed at or below a given value. It climbs from left to right and ends at 100 percent, which makes it the right chart for reading off a statement like '99 percent of loops were within this'.

Box plot — Summarises a whole distribution in one shape. The line inside the box is the median, the box holds the middle half of the data, and the whiskers reach most of the rest. It shows spread, which a single average hides.

Pareto front — Accuracy plotted against what a model costs to run, one point per candidate. It is used when there is no single best answer, only a set of them: a model is on the front if nothing else is both more accurate and cheaper. The useful reading is not which point is highest but how much accuracy the next step down the cost axis actually buys, which is frequently very little.

Logarithmic axis — An axis where each step is a multiplication rather than an addition, so 0.1, 1, 10, 100 are evenly spaced. It is used when the numbers span orders of magnitude. On an ordinary axis, values of 23 percent and 0.01 percent cannot both be visible; on a logarithmic axis they can.

Error bars and strip plots — Individual runs drawn as dots so that every one can be seen, with a bar showing the confidence interval and a tick at the mean. If two groups' bars overlap heavily, the two groups are not meaningfully different.


## One convention used throughout, and it reverses a conclusion

Several charts report energy on a comparable scale rather than as raw consumption. A controller is free to turn the cabin heating down to save energy, and measured in plain watt-hours it looks excellent for doing so. But that is the same trick as driving more slowly: it buys the number by giving up something the driver actually wanted.

So wherever a controller sheds cabin heat, that energy is added back at exactly what shedding it saved, and both numbers are always shown. The gap between them is how much comfort the controller spent. The correction is not cosmetic. Without it the week 8 result reads as the learned controller saving 1.3 percent. With it, the same controller is 0.66 percent worse than hand-written rules.


# 5. Why the project is organised around gates

A gate is a measurement taken early, with a decision attached to it in advance. The compute budget is measured in week one, not week ten, because a Transformer that turns out to be twenty times too slow leaves no time to recover if the discovery comes late. Each gate has a written action for failure, so a bad result redirects the work instead of stopping it.

This matters for how the project reads. Several results below are negative. None of them was a setback, because each had a planned response, and in two cases the negative result is more interesting than the positive one would have been.


# 6. The vehicle model

The vehicle model is the foundation. If it cannot reproduce a real drive, nothing built on top of it means anything, which is why gate G2 stops all other work until it does.


## The data

Measurements come from a public archive of a 2014 BMW i3 driven in Munich, recorded ten times a second: battery voltage and current, state of charge, ambient temperature, elevation, and heater power. Thirty-three trips passed the eligibility rules. They were split by trip, never by row, into 19 for training, 7 for tuning and 7 sealed for the final test. The sealed trips have not been opened.


## What the model had to prove

The test replays a held-out trip's recorded speed through the model and compares predicted battery power and state of charge against what was actually recorded. The original pass mark combined three separate models into one number, and when it failed there was no way to tell which of the three was at fault. The design document allows one revision of this criterion, and it was spent here.

Neither threshold was loosened. What changed is which model each threshold applies to. Splitting the test showed the problem immediately: the battery and motor models were fine, and the error came from working out acceleration by differentiating a recorded speed signal, which amplifies noise. Three independent checks confirmed it was noise rather than a modelling mistake, including the fact that trips with smoother driving scored worse, which is the opposite of what a model defect would do.

| Part | What is tested | Threshold | Result |
|---|---|---|---|
| A | Torque worked out from recorded speed | within 50% of spread | 7 of 7 pass |
| B | Battery power, given recorded torque | within 10% of mean power | 7 of 7 pass |
| C | State of charge at the end of the trip | within 2 percentage points | 6 of 7 pass |

Figure 1. Gate G2. Each panel is one part of the split criterion, with the pass threshold marked. Splitting the original single number is what made the failure attributable.

Left panel — every trip plotted against both thresholds at once. Horizontal axis is the battery-power error as a percentage of that trip's own average power; vertical axis is the error in battery charge at the end of the trip, in percentage points. Each dot is one held-out trip, labelled with its number. The two dashed lines are the thresholds, so the pass region is the rectangle below and to the left of both. Plotting two criteria on two axes rather than as two separate charts shows at a glance which criterion a trip is close to failing, and whether any trip is marginal on both at once.

Right panel — the evidence for splitting the criterion in the first place. Two horizontal bars per trip. The dark bar is the torque part of the gate, as a percentage of that trip's own torque variation; the grey bar is the single pooled number this criterion replaced, shown for contrast and not itself gated. The dashed line at 50 percent is the torque bound. The gap between the two bars is the whole argument for the revision: the pooled number was dominated by noise from one specific step, not by a bad model.

Reading it: every trip clears the torque bound and every trip is left of the 10 percent power line. One trip sits above the 2 percentage point line at 2.45, missing by 0.45 of a point. Six of seven pass, and that miss is reported rather than rounded away.

The one failure misses by 0.45 of a percentage point and is traceable to road-load differences between trips rather than to the physics. It is worth being exact about what that means for the gate, because the temptation is to call six out of seven a pass. The criterion says every validation trip, both thresholds were deliberately carried over unchanged when the criterion was split, and one trip is outside one of them. So the gate's own verdict is a fail, and it is recorded as a fail in the measurement file.

What followed was a decision rather than a re-reading. Phase 2 was allowed to begin with the miss recorded and a condition attached: the forecaster is trained on real logged trips rather than on plant output, so its validity never depended on this gate, and the plant's real job is the reinforcement-learning environment and the closed loop. The trip-to-trip road-load spread, roughly 10 percent on mechanical energy, was to be represented as randomised training conditions rather than a fixed parameter set. That condition is still open and appears in the decisions list.


## Is the model right everywhere, or only on average?

An average error can hide a model that is systematically wrong. Being consistently 10% high while accelerating and 10% low while braking averages out to nothing and is a broken model. The next two figures exist to expose that, and neither can be replaced by a summary statistic.

Figure 2. Predicted against actual battery power, for the best and the worst held-out trip. A perfect model puts every point on the diagonal.

Left panel — the best-performing held-out trip. Horizontal axis is the battery power the real car recorded; vertical axis is what the simulation predicted, both in kilowatts. Every dot is one tenth-of-a-second sample, thousands of them, drawn semi-transparent so that density is visible. The diagonal line is the ideal, where prediction equals reality. The panel title carries that trip's error both in kilowatts and as a percentage.

Right panel — the worst-performing held-out trip, on identical axes. The same construction at the same scale, so the two are directly comparable by eye. Showing the best and the worst rather than a typical pair is deliberate: the best alone would flatter the model and the worst alone would misrepresent it.

Reading it: both clouds sit along the diagonal with no visible bend or S-shape, and that matters more than how wide the cloud is. Width is measurement noise; a bend would be a real modelling error, such as the efficiency map being wrong at high torque. Note that the points extend well into negative power on both axes. That is regenerative braking, energy flowing back into the battery, and the plant reproduces it.

Figure 3. The same comparison along the timeline of an actual drive, so an error can be traced to the moment that produced it.

Top panel — what the car was doing. Horizontal axis is time in seconds; vertical axis is speed in kilometres per hour. This is the real logged speed profile of the drive, and it is the context strip: accelerations, cruises and stops are all visible. The two panels below share this exact time axis, so any feature can be read straight down the figure.

Middle panel — predicted against actual battery power. Two traces overlaid on the same time axis: what the real car drew, and what the plant predicted. Positive values are discharging to drive the car; negative values are energy being recovered under braking. This panel is drawn taller than the others because it is the comparison the gate is about.

Bottom panel — the error on its own, so that it can be seen at all. The difference between the two traces above, with a line at zero. Separating it out matters: when both traces are swinging across 60 kilowatts, a 3 kilowatt error is invisible in the overlay and obvious here.

Reading it: compare the bottom panel against the top one. The error spikes line up with hard accelerations and hard braking, and falls close to zero during steady cruising. That is the signature of a differentiation artefact rather than a wrong parameter. Working out acceleration from a 10 Hz speed signal and multiplying it by 1,270 kilograms amplifies sampling noise exactly at the moments when speed changes fastest, whereas a wrong parameter would produce an offset that persists through the cruise. This panel is the direct evidence behind splitting the gate criterion.


## Seven faults the gate caught

The gate did its job. Five of the seven faults it exposed would have corrupted every downstream result without ever announcing themselves. The battery current sign was inverted. The motor model returned zero torque above a speed the car actually reaches, so it read zero power exactly where the car drew the most. The efficiency map was assumed rather than measured, and the assumed one was 7.4% pessimistic.

The instructive one is the motor speed limit. It came from a published top speed of 150 km/h combined with a calculated wheel radius, and the archive shows the car reaching 152.3 km/h. A brochure figure and a measured envelope are not the same thing.


# 7. A finding that changes what the paper may claim

Four numbers in the vehicle model were fitted to the data rather than looked up: rolling resistance, drag coefficient, internal battery resistance and a rotating-mass factor. Each was placed in the slot of the physical quantity whose behaviour it shares.

Testing the model against a second dataset, a Nissan Leaf recorded in Michigan, revealed the problem. Fitting against the i3 gives a rolling resistance of 0.01947. A coastdown test on a comparable electric car measures 0.00878. That is a factor of 2.2, and rolling resistance does not vary by a factor of 2.2 between passenger cars on the same roads.

The extra amount is drivetrain drag, brake drag, efficiency-map error and any standing electrical load the model does not account for separately. Those losses have to go somewhere, and least squares puts them in the term whose shape fits. The number is a lumped loss coefficient wearing the name of rolling resistance.

The consequences are binding and the parameter file now records them. The paper must describe these four as fitted coefficients, never as measured vehicle properties, because a reviewer who reads 0.01947 as a rolling-resistance measurement is entitled to reject it. They are also not transferable between vehicles as physical constants, which the next section quantifies.

This does not weaken the vehicle model. Gate G2 asks whether predicted power and charge match recorded values, and fitted coefficients that reproduce recorded power are exactly what a simulator needs. What they do not support is a claim about the coefficient itself.


# 8. Does the model transfer to a different car?

The question was tested three ways on 89 held-out Nissan Leaf trips, so that a failure would be attributable rather than merely observed.

| Arm | What it uses | Energy error | Charge error |
|---|---|---|---|
| A | Everything transferred from the i3 | 16.9% | 1.45 pp |
| B | The Leaf's own measured road load | 14.4% | 0.99 pp |
| C | Refitted on Leaf data (the ceiling) | 13.4% | 0.89 pp |

Transfer costs 3.5 percentage points of energy error compared with fitting in place. Substituting the Leaf's own coastdown measurement recovers 2.5 of those points and nine of the twelve trips that failed the charge criterion. That is the price of carrying one car's unmodelled losses into another car.

One error appears in all three arms and none of them fixes it. Energy error slopes from minus 16% below freezing to plus 16% above 24 degrees, even when the model is fitted in place. Cold trips draw 239 Wh per kilometre against 133 for warm ones, and the recorded auxiliary channel accounts for only about 2 kW of the implied 3.2 kW. The rest is battery heating, stiffer tyres and a less efficient pack. A model with temperature-independent parameters cannot represent it.

Arm A has the steepest temperature slope, and the reason is worth stating. Its inflated rolling resistance over-predicts everywhere, the missing cold-weather load under-predicts in the cold, and near zero degrees the two cancel. A model that is right for compensating reasons is not right.

Figure 4. Cross-vehicle transfer. Left: energy error by arm. Middle: charge error against the two-point criterion. Right: the temperature slope that no arm removes.

Panel A — how much energy error each arm makes, as a distribution. Vertical axis is absolute trip energy error in percent. Each arm gets a box summarising the middle half of the 89 trips, with the median as a line, and every individual trip scattered over it as a faint dot. Showing the dots as well as the box is deliberate: a box alone cannot say whether a wide spread is a few bad trips or a genuinely broad distribution.

Panel B — how many trips land inside the charge criterion. Horizontal axis is end-of-trip charge error in percentage points; vertical axis is the percentage of trips at or below that error. Read it as 'this fraction of trips were this good or better'. The dashed vertical line at 2 percentage points is the same criterion gate G2 used, carried over so both datasets are judged by one standard. A curve that climbs early is a good arm.

Panel C — the residual that none of the three arms removes. Horizontal axis is outside air temperature in four bands from minus 20 to plus 40 degrees; vertical axis is the median signed energy error. Signed rather than absolute, so over-prediction and under-prediction separate instead of cancelling out.

Reading it: panel A gives medians of 16.9, 14.4 and 13.4 percent, so transferring everything costs 3.5 points over refitting in domain and substituting the Leaf's own road load recovers 2.5 of them. Panel B puts 55, 64 and 67 of 89 trips inside the criterion. Panel C is the real finding: every arm slopes with temperature including the re-identified control, and since that control was fitted on this very data the slope cannot be a failure of transfer. It is a real thermal effect that a fixed-parameter plant cannot track. Without the control arm in the picture it would have been misread.

The honest limits: three cars in one city, so transfer to a Leaf is not transfer to any electric vehicle. The coastdown describes the model of car, not these specific units, whose battery packs measure 42 Ah against a 66.2 Ah nameplate because they are five years old. And there is no battery temperature channel, so the model runs on ambient temperature, which errs toward an optimistically warm pack.


# 9. Checks run before any model was trained

Three checks had to pass before a single model was fitted, because each one decides whether later numbers mean anything.


## Can the model see its own answer?

The target is battery power, which is voltage times current, and both of those are inputs. That is not a leak: the model reads them up to the end of its input window and is asked about power from the following sample onward, which is the forecasting problem. It would become a leak the moment a window's inputs and its targets shared a single sample, so the window arithmetic prevents that and an automated test checks it on the sample index rather than trusting a comment.


## Does the pipeline learn from scrambled answers?

Targets were shuffled and the model retrained. It scored minus 0.0044, which is chance, as an honest pipeline should. The same wiring on real targets scores plus 0.4018. Both numbers are reported together on purpose: a scrambled-target check on a pipeline that cannot learn anything also returns zero, for reasons that have nothing to do with leakage.


## What does doing nothing achieve?

The naive baseline predicts that battery power stays where it is. Three seconds ahead that gives 13.219 kW of error, which is larger than the average size of the signal itself. That is what makes the problem worth solving.

Figure 5. Baselines before any model was trained. Left: error grows with how far ahead the model looks. Middle: nothing survives three seconds intact. Right: a linear regression already clears the gate.

Left panel — error grows with how far ahead you look. Horizontal axis is the forecast horizon from 0.1 to 3.0 seconds; vertical axis is prediction error in kilowatts. Three baseline methods are drawn, plus a dashed line marking the bar gate G4 sets, which is 10 percent below the naive baseline at every step.

Middle panel — how much of reality each method actually explains. Same horizontal axis; vertical axis is R-squared, the fraction of real variation explained. The line at zero is the level of simply guessing the average every time. Anything below it is worse than useless.

Right panel — the uncomfortable one. Just the linear model, plotted as how much better it is than the naive baseline, against two reference lines: zero, and the dashed line at 10 percent which is exactly what gate G4 demands.

Reading it: error climbs from 0.86 kW at a tenth of a second to 13.2 kW at three seconds, a factor of fifteen. The naive baseline explains 99.7 percent of the variation at a tenth of a second and only 18 percent at three, while extrapolating the current trend reaches minus 2.2, which means it is considerably worse than assuming nothing changes. The right panel is the finding: the linear model ends at 14.5 percent, above the 10 percent requirement, so a 257-number model passes gate G4 before any proposed model exists.

A second naive method, extrapolating the recent trend in a straight line, is worse than doing nothing beyond about half a second and twice as bad at three seconds. Battery power reverts rather than continues, because the thing being predicted is driver intent and driver intent does not trend. Linear extrapolation is the first thing anyone reaches for, so it is worth knowing that it hurts.


# 10. The forecasting models

Six methods were compared on the same windows: 3.2 seconds of history at ten samples a second, predicting the next 3.0 seconds of battery power. Every model is scored on the tuning trips. The sealed test trips remain closed.

| Method | Error at 3 s | R squared | Better than doing nothing |
|---|---|---|---|
| Do nothing (persistence) | 13.219 kW | 0.183 | baseline |
| Extrapolate the trend | 26.172 kW | -2.204 | much worse |
| Linear regression | 11.308 kW | 0.402 | 14.5% |
| XGBoost | 11.290 kW | 0.404 | 14.6% |
| LSTM | 11.120 kW | 0.433 | 15.9% |
| Transformer | 11.029 kW | 0.442 | 16.6% |

Figure 6. The model comparison. Rightmost panel is where the deployment decision is made: accuracy against time on the chip, with the 40 millisecond budget marked. Crosses do not fit.

Panel 1 — the whole comparison, against horizon. Horizontal axis is the forecast horizon; vertical axis is error in kilowatts. All five arms on one axis. Mostly useful for seeing that the trend-extrapolation method is catastrophic and that the other four bunch tightly together, which is itself the story.

Panel 2 — the same arms measured against the linear model instead. The linear model becomes the dashed zero line and everything is replotted relative to it. This is the comparison that can actually separate the arms, because measuring against the naive baseline flatters all of them equally.

Panel 3 — broken down by individual trip. Horizontal axis is the seven validation trips; vertical axis is error at the three-second horizon. Three bars per trip. Seven trips is few enough to show every one rather than an average, which is the direct fix for a defect in the predecessor work where the figures and the tables disagreed.

Panel 4 — the panel the deployment decision is actually made on. Horizontal axis is estimated time per prediction on one chip core, on a logarithmic scale; vertical axis is error. Each arm is one point. A circle means it fits the budget and a cross means it does not. The dotted horizontal line is the naive baseline, which is free and which every model must get under to justify itself. The dashed vertical line is the 40 millisecond budget.

Reading it: against the linear model, the naive baseline is 17 percent worse, XGBoost is 0.2 percent better and the LSTM's 1.7 percent advantage appears only in the far half of the horizon. Panel 3 is quietly important, because the bars vary more between trips than between models: which trip you evaluate on matters more than which model you use. Panel 4 is where two arms leave the running, and it is the panel most papers omit.

Figure 7. Left: error against how far ahead the model predicts. Second: every model measured against the linear regression. Third: what the physics term bought. Right: how the residual weight trades accuracy against physical consistency.

Panel 1 — the Transformer placed against everything before it. Horizontal axis is the horizon; vertical axis is error. The dotted line is the naive baseline and the dashed line the LSTM, both carried over from the previous figure so the comparison is direct. The three solid lines are Transformer variants.

Panel 2 — the ablation itself, with every seed shown. Two columns, plain and physics-informed; vertical axis is error at three seconds. Three dots per column, one per random seed, with a bar at the mean. Individual seeds are drawn rather than only an average because with three runs the spread is the result, and an average alone would imply more precision than three runs support.

Panel 3 — what the physics penalty actually bought. Horizontal axis is the three physical laws; vertical axis is violation size relative to the plain model, which is normalised to 1.0 for each law. Normalising is necessary because the three quantities are in watts, per second and volts, three different units that cannot otherwise share an axis. The multiplier is printed above each bar.

Panel 4 — the dial that trades one against the other. Horizontal axis is the strength of the physics penalty on a logarithmic scale. Two series on two different vertical axes: accuracy on the left, physical consistency on the right. The dashed vertical line marks the setting chosen, 0.1.

Reading it: panel 2 is a null result, with the two columns overlapping almost completely and a difference of about five watts on eleven kilowatts. Panel 3 is not a null: the electrical law improves to 0.37 times the plain model's violation and terminal voltage to 0.60 times, but the third law gets worse at 1.65 times. That is why panel 3 exists. Plotting accuracy alone would have reported this ablation as a plain failure, when the honest answer is that the physics term buys physical consistency rather than accuracy, and that one of the three laws is unusable at this horizon.


## What the comparison shows

The Transformer is the most accurate, and it is also the narrowest margin in the table: 0.8% better than the LSTM and 2.5% better than a linear regression. Retraining with different random starts moves each model by about as much as the gaps between them, so the ordering of the top three is supported but not commanding.

XGBoost, with 15,103 decision trees, finishes 0.2% ahead of a regression with 7,710 numbers in it. Tuning its settings does not change that. Whatever can be predicted about battery power three seconds ahead from this window is close to linear, and the rest is the driver.

The LSTM is worse than the linear regression for the first second and better after about 0.9 seconds. Near-term power is almost decided by the last measurement, which a linear map reads directly. Further out, the last measurement stops being enough.

Which trip you are driving matters more than which model you run. Every model scores about 6.7 kW on the easiest trip and about 15.5 kW on the hardest.


## Gate G4, and why passing it proved less than expected

The gate asks for a model that beats the naive baseline by 10%. Before any of the proposed models existed, a plain linear regression already beat it by 14.5%. A Transformer clearing the same bar would have demonstrated nothing a single matrix calculation did not.

Two responses. Every model is now reported against the regression as well as against the naive baseline, which costs nothing and turns 'beats the baseline' into a statement with content. And a proposal to restate the gate as 10% over the regression has been recorded in the design document for the gate itself to decide, because changing a threshold belongs there and not in a results file.


# 11. The physics-informed model, and what it actually buys

A physics-informed model is trained on two things at once: matching the recorded data, and obeying equations that must hold whatever the data says. Making that meaningful required the model to predict a full electrical state rather than power alone, because power on its own has nothing to be consistent with. It now predicts power, current, voltage and charge together, and three equations tie them to each other.

Ablation A1 compares the plain and physics-informed versions at an identical 21,336 parameters, with identical random starts. The only difference is the loss. An automated test checks the parameter counts match, so the comparison cannot quietly become a test of model size.


## The answer on accuracy is no

| Version | Run 1 | Run 2 | Run 3 | Average |
|---|---|---|---|---|
| Plain | 11.098 kW | 11.073 kW | 11.001 kW | 11.057 kW |
| Physics-informed | 11.114 kW | 11.101 kW | 10.940 kW | 11.052 kW |

Five watts of difference on eleven kilowatts. Physics-informing does not make the forecast more accurate. The design document accepted this outcome in advance, which is what makes reporting it straightforward rather than awkward.


## The answer on consistency is yes, by a wide margin

| Check | Plain | Physics-informed | Change |
|---|---|---|---|
| Power disagrees with voltage times current | 24.5% of steps | 2.5% of steps | 10x fewer |
| Average size of that disagreement | 373 W | 139 W | 2.7x smaller |
| Voltage disagrees with the battery model | 8.40 V | 5.00 V | 1.7x smaller |

A model whose predicted power, current and voltage disagree with each other by 373 watts on a quarter of its steps is not wrong about power, but it is not describing a battery either, and the controller downstream reads more than the power channel. The honest statement of A1 is that the physics term is a consistency mechanism rather than an accuracy mechanism, and the paper should claim it as one.


## One equation had to be switched off, and the data says why

The second equation states that charge falls in proportion to the current drawn. It is disabled, and the reason is a property of the recording rather than of the physics.

The recorded state-of-charge channel holds its value across 95.8% of consecutive samples. It moves in bursts, with gaps of one sample when it moves and 75 or more when it does not, up to 59 seconds. The measured consequence: the median three-second window in this archive contains exactly one distinct charge value. Recorded charge change over such a window is zero, against a physically implied 0.00022.

So the data pushes predicted charge to stay flat, because flat is what the instrument records, while the equation pushes it to fall. They disagree, and the disagreement is caused by the recording rate. That was an argument until it was measured: switching the equation on costs 4.4% of accuracy, moves its own violation rate only from 0.988 to 0.966, and gives back part of the consistency gain elsewhere.

Charge conservation is a real constraint and it is not being dismissed. It is testable over minutes, which is the trip-energy check gate G2 already performs. It is not testable over three seconds on a channel with this resolution.

A third equation was substituted for a different reason. The design document writes it in terms of future mechanical power, which is not recorded, is unavailable when the model runs, and could only be reconstructed by putting the vehicle simulator inside the training loop. The battery relation the project had already validated stands in for it: terminal voltage must equal open-circuit voltage at the predicted charge, less the drop across the internal resistance. It constrains the same three quantities and the recorded data supports it.


# 12. What each model costs on the chip

Accuracy without cost is half a result. The deliverable is a forecaster running on an ESP32-S3, so every model is costed at the moment it is scored, against a throughput measured on the actual chip in week one: 29.82 million multiply-accumulate operations per second on one core. Gate G5 allows 40 milliseconds and 300 kilobytes.

| Model | Error at 3 s | Time on one core | Share of budget | Size | Fits |
|---|---|---|---|---|---|
| Do nothing | 13.219 kW | 0.00 ms | 0% | 0.0 KB | yes |
| Linear regression | 11.308 kW | 0.26 ms | 1% | 7.5 KB | yes |
| XGBoost | 11.290 kW | not applicable | n/a | 3657.8 KB | NO |
| LSTM, one model | 11.120 kW | 19.84 ms | 50% | 20.4 KB | yes |
| LSTM, 5-model average | 11.007 kW | 99.22 ms | 248% | 102.0 KB | NO |
| Transformer | 11.029 kW | 22.28 ms | 56% | 17.9 KB | yes |
| Transformer, physics-informed | 11.052 kW | 22.38 ms | 56% | 20.8 KB | yes |


## Two rows changed what can be claimed

XGBoost is not deployable. At roughly 3.7 megabytes it exceeds the 300 kilobyte budget by more than twelve times, and that is with a deliberately generous estimate of how compactly a decision tree can be stored. It stays in the comparison as an offline reference, since it answers whether a strong tabular method would have done better, and the answer is no. No amount of accuracy would have made it a candidate for the chip.

The best LSTM figure was not a deployable figure. It came from averaging five separately trained models, which costs five times the time and memory and misses the budget by a factor of two and a half. What can actually be programmed onto the chip is one model, and the report quotes that number. Presenting the average as though it were the deployed result would repeat one of the faults found in the earlier work.

The Transformer fits, at 56% of the time budget and 6% of the memory budget. That outcome was not guaranteed. The configuration the original plan implied would have needed 175.8 milliseconds and would not have fitted at all. Measuring the chip in week one is what made the difference.

Read across the table and the trade is visible. The linear regression reaches 87% of the achievable benefit for 1.2% of the computing cost. Whether the last 2.5% is worth 22 milliseconds is a question the controller experiments answer, not this section. Either way the trade-off curve is itself one of the results the project set out to produce.


# 13. Measuring it on the chip

The previous section estimated what each model costs by dividing its multiply count by a speed measured on the chip in week one. This section measures the model itself, and the two answers differ enough to matter.


## The estimate was 64% low

The forecaster's exact shape was written out in C using 8-bit arithmetic and timed on the ESP32-S3. One prediction takes 36.46 milliseconds. The estimate was 22.28. The measurement repeats to a tenth of a microsecond across resets and across reprogramming the chip.

|  | Time for one prediction | Share of the 40 ms allowed |
|---|---|---|
| Measured on the chip | 36.46 ms | 91% |
| Estimated from the multiply count | 22.28 ms | 56% |

The reason is straightforward once measured. Counting multiplications prices the multiplications and nothing else. The model also has to compute a softmax, which needs 1,024 exponentials for each of four attention heads in each of two layers. That takes 7.25 milliseconds, a fifth of the whole forward pass, and the estimate assigned it zero. Layer normalisation adds another 0.64.

The same measurement was made for the LSTM, and it settles what the gap is evidence of. The LSTM has no softmax, so if attention were the explanation its estimate should have been close. It is further off, not closer.

| Model | Estimated | Measured on the chip | Ratio |
|---|---|---|---|
| Transformer | 22.28 ms | 36.46 ms | 1.64x |
| LSTM | 19.84 ms | 35.07 ms | 1.77x |

Four gates over 64 units on each of 32 timesteps is 8,192 sigmoid and tanh evaluations, which is the same order of non-multiply work under a different name. The estimating method was optimistic, not the architecture, and that is the more useful finding because it applies to every model in the comparison and to any added later.

It also changes the choice between the two. Estimated, the LSTM looked 11% faster than the Transformer. Measured, it is 4% faster, for 0.8% worse accuracy. That is close enough that the controller experiments should decide it rather than the forecasting numbers alone.

The multiply rate itself holds up. The largest matrix multiplication runs at 28.1 million operations per second against the 29.82 measured on a synthetic loop in week one, a 6% difference in the direction real memory access would push it. The week-one measurement was right about multiplications. It was the assumption that multiplications are the whole cost that was wrong.

This is worth stating carefully, because it is a good result rather than a bad one. The model still fits, at 91% of the budget, and this is the slowest way it could possibly be written: plain C with no use of the chip's vector instructions, and a floating-point exponential for every attention weight. Both of those have well-understood fixes. The 36.46 milliseconds is a ceiling, not a floor.


## Shrinking the model to 8-bit numbers costs 0.95%

| Version | Error at 3 s | Better than doing nothing | Size |
|---|---|---|---|
| Full precision | 11.051 kW | 16.4% | 71.7 KB |
| 8-bit | 11.156 kW | 15.6% | 20.2 KB |

The model becomes 3.56 times smaller and loses 0.95% of its accuracy. It still clears the required 10% improvement with half again as much margin as it needs. Nothing here suggests the harder alternative, retraining the model to be aware of its own rounding, is necessary.

The memory figure has an independent check behind it. A cost calculation written from the model's shape predicts 20,664 bytes, and counting the real quantised network gives 20,664. The two were written separately and they agree exactly.


## A mistake worth recording

The first version of the quantisation code selected which numbers to shrink by looking at the type of each layer. That silently skipped the attention block's input projection, because PyTorch stores it as a bare array rather than as a layer, and it also failed to catch the attention output because that projection is applied without going through its own layer object. Between them, a third of the model stayed at full precision and the reported cost of shrinking it would have been far too low. Both gaps are now covered and both are held in place by tests.

What is still missing for the full gate is the standard conversion toolchain, which is not installed on this machine. That toolchain would add interpreter overhead, which makes things slower, and bring optimised vector routines, which make them faster. Neither effect is guessed at here. What these two measurements establish is that the model fits with room to spare and that 8-bit precision is survivable, which is what decides whether the conversion work is worth starting.


# 14. Whether a bigger model, taught to a smaller one, helps

The design document plans this experiment in three rungs: the model in full precision, the same model in 8-bit, and then a small model taught by a large one. The first two were measured in week 6. This is the third, and it is the last piece of that experiment.


## The question is narrower than it sounds

Whether a big model beats a small one is not the question and would not be interesting. The forecaster that runs on the chip is already the size the compute budget allows, and it is trained on the data directly. The question is whether that same small model, taught by a large one instead of by the data alone, comes out better. Same size, same starting conditions, one difference.

Teaching a small model with a large one is called distillation. The large model, the teacher, is deliberately too big for the chip: if it fitted, there would be nothing to distil into. The small model is then trained on a half-and-half mixture of the real answer and the teacher's answer.


## First, a check that this is the same model

This experiment builds its data and trains its models with a separate script from the one week 6 used, so before any comparison means anything, its unchanged arm has to reproduce the model week 6 already measured. It does, to every digit.

| Quantity | Week 6 | This run |
|---|---|---|
| Error, full precision | 11051.0667 W | 11051.0667 W |
| Error, 8-bit | 11155.7240 W | 11155.7240 W |
| Size on the chip | 20,664 bytes | 20,664 bytes |


## The answer is no

| Model | Distilled minus direct | Per training run | Across runs |
|---|---|---|---|
| d32 | +21.9 W (+0.20%) | -13, +64, +15 | sign flips |
| d16 | +99.2 W (+0.89%) | +134, +166, -2 | sign flips |

A negative number would mean distillation helped. Both are positive, and neither keeps its sign across the three training runs. By the same standard this project used to call the forecast ablation empty, this is empty too.


## Why, and this is the part worth keeping

The teacher is not better than its students. It carries 26.7 times as many parameters and 23.1 times the memory of the smallest student, and it comes out 64.3 watts WORSE. Distillation moves what the teacher knows and the student does not, and here that is nothing. The empty result is the method reporting honestly that there was nothing to move, rather than the method failing.

Figure 8. Accuracy against cost for every arm, and the same comparison paired by training run. Note how far the error bars overlap: that overlap is the result.

Left panel — accuracy plotted against what each model costs to run. Each column is one model size, with the directly trained and the distilled version at the same position because they are the same size and cost the same. The grey line joins each pair, so the vertical gap between the two dots is the whole effect of teaching. The bars are the spread across three training runs, and they overlap almost completely.

Right panel — the same thing, run by run. Each dot is one training run: how much worse or better the taught model was than the untaught one. Dots on both sides of the line mean the effect changes direction depending on the random seed, which is what having no effect looks like.


## What the whole comparison is worth

Every model tried, from 5,102 parameters to 136,414, falls within 99.2 watts of the others, which is 0.89%.

That is smaller than what 8-bit conversion costs, measured in week 6 at 0.95%. The entire range of model sizes matters less than the number format does.

The distance from the best model to the naive baseline is 2,071 watts. So the whole sweep of architectures moves 4.8% of the distance that having a forecaster at all buys.

This is the third time the project has arrived at that shape from a different direction. The model comparison in week 4 found a plain linear regression reaching 87% of the benefit for 1.2% of the cost. The offline optimum in week 7 found the best possible energy strategy was a constant. Now the model sweep finds capacity beyond a very small network buys nothing. The useful signal in this problem is captured early and cheaply.


## What it changes, and what it does not

It does not settle what should ship. That decision is waiting on the energy-management question in section 16. What it adds is a cheaper option that was not on the table.

The half-width model reaches 11.148 kW using 6.1 KB, against the deployed model's 11.156 kW using 20.2 KB. Those two are the same number to within the noise between training runs, so if the forecaster ships at all, nothing measured here justifies paying for the larger one.

One caution attaches to that. The latency figures in this section are estimates from counting arithmetic, and this project has already measured what such estimates are worth: the deployed model was estimated at 22.28 milliseconds and timed on the chip at 36.46, so the estimate ran 64% low. The smaller model would need timing on the board like everything else before its figure is quoted.


# 15. The real-time loop on hardware

Gate G3 asks whether the control loop actually closes on the hardware: the microcontroller requests the vehicle state, receives it, computes a command and sends it back, one hundred times a second. The pass mark is that 99% of loops land within one millisecond of their ten-millisecond slot, with no frames lost, over ten minutes.

The microcontroller keeps the timing, not the laptop. macOS is not a real-time system, so timing measured on the host would record the host's own scheduling noise rather than the loop's. The chip therefore builds a histogram of its own loop periods and reports it over the link, and the laptop measures only what only the laptop can see, which is frames that never arrived.

| Measurement | Result | Requirement |
|---|---|---|
| Control loops completed | 59,650 | - |
| Timing spread, median | within 25 us | - |
| Timing spread, 99th percentile | within 25 us | 1000 us |
| Timing spread, 99.9th percentile | within 25 us | - |
| Loop period range | 9845 to 10011 us | 10,000 nominal |
| Control computation, worst case | 97 us | under 10,000 |
| Picking up a waiting reply, worst case (not a round trip) | 1766 us | - |
| Frames lost | 3 | 0 |

Gate G3: FAIL on the frame criterion, and a pass on timing by a factor of 40.

Figure 9. Loop timing over ten minutes. Left: how many loops landed in each timing band, on a log scale. Right: the same data cumulatively, against the gate limit. Everything lands in the first two bands.

Left panel — how many loops landed in each timing band. Horizontal axis is how far each loop's actual period strayed from a perfect 10 milliseconds, sorted into thirteen bands from 'within 25 microseconds' up to 'more than 5 milliseconds'. For scale, 25 microseconds is a quarter of one percent of the period. The vertical axis counts loops on a logarithmic scale, because otherwise a band holding one loop and a band holding sixty thousand cannot both be visible, and the rare cases are exactly what a deadline study is about. Bars inside the limit and outside it are coloured differently.

Right panel — the same data as a running total, against the limit. Same horizontal bands; vertical axis is the cumulative percentage of loops, zoomed to the range 90 to 100 percent because everything interesting happens in the top tenth. The dashed horizontal line marks 99 percent, which is the level the gate is written against, and the dashed vertical line marks the 1000 microsecond limit.

Reading it: everything lands in the first band. The 99th percentile is 25 microseconds against a 1000 microsecond limit, so the loop passes its timing criterion by a factor of forty, and on the right panel the curve has already reached the top before it gets anywhere near the limit line. What fails the gate is not the loop. The gate also demands zero lost messages, and a handful of those were the laptop answering late.


## Which side failed

The evidence separates them cleanly, and the answer is not the part being tested.

The link carried everything. No corrupted frames at either end and no gaps.

The microcontroller met every deadline. Its control computation runs in 97 microseconds inside a 10,000 microsecond slot, and the count of loops that missed their own deadline is 0.

What missed, 3 times in 59,650 loops, was the laptop answering in time.

The misses are not spread evenly. They arrive in short bursts on an otherwise idle laptop, which is macOS doing something else rather than a steady overload.


## The fix was built, not deferred

The original loop sent a request and waited for the reply inside the same ten-millisecond slot, which ties its deadline to the scheduling behaviour of a general-purpose operating system. The control task now requests the next state, acts on the most recent state it already holds, and reads replies without waiting. Both versions build from the same source behind a compile-time switch, so the comparison is a rebuild and both stay measurable.

| Over 59,650 loops, ten minutes | Original | Pipelined |
|---|---|---|
| Timing spread, 99th percentile | within 25 us | within 25 us |
| Wait for a reply, worst case (see below) | 7,405 us | 77 us |
| Replies that arrived too late | 6 | 0 |
| Steps using a state one period old | not applicable | 8 |
| Corrupted or lost frames | 0 | 0 |

An earlier version of this report said the round trip fell by a factor of 96. That compared two different things, and is withdrawn. In the original loop the chip waits for the answer to the request it has just sent, so 7,405 microseconds is a true round trip. In the pipelined loop the answer it reads is the reply to the previous request, which has usually been waiting for most of a period, so 77 microseconds is only how long it took to pick up a reply that was already there. The true round trip in the pipelined loop was not measured. What does stand is the point of the change: the loop no longer waits for the laptop inside its own time slot. The timing is unchanged, which is the expected result: the loop was never the problem.

A handful of events survive and the gate still fails. What changed is what an event costs. In the original loop a miss meant the control task had spent nine of its ten milliseconds waiting and received nothing, so the loop itself was at risk. In the new loop a miss means the controller acted on a state one period older than intended, and the loop was never in danger. Same criterion, completely different failure.

The question the gate now has to settle is whether its criterion should separate the two. A loop that misses its own deadline is a defect, and there are none of those in either version. A laptop that answers late is a property of running the simulation on macOS, and there are a few of those, bounded and handled. Reading both as the same failure leaves the criterion unable to tell a working system from a broken one. Zero over ten minutes at a hundred times a second against an ordinary operating system may not be reachable at all, and that is worth reporting as a finding rather than treating as a defect.

This is also the project's own subject matter. One of the planned experiments compares deadline-miss handling switched on against off, and a test rig that never missed a deadline would leave it nothing to measure.

The criterion has not been loosened to fit the result. One revision of one criterion was permitted in the design document, it was used at gate G2 with the reason recorded, and it is spent.


## Re-measured in week 7, on firmware that changed

The loop is not the loop that was measured in week 3. It now runs a real speed controller with a physics feedforward instead of a placeholder, and both message formats grew to carry the extra signals that controller needs. The rule in this project is that the loop the paper reports has to be the loop that was measured, so the ten-minute campaign was run again in full.

| Over 59,650 loops, ten minutes | Week 3 | Week 7 |
|---|---|---|
| Timing spread, 99th percentile | within 25 us | within 25 us |
| Control computation, worst case | 16 us | 97 us |
| Picking up a waiting reply, worst case (not a round trip) | 77 us | 1766 us |
| Loops that missed their own deadline | not counted | 0 |
| Laptop answered late | 8 | 3 |
| Corrupted or lost frames | 0 | 0 |

The control computation rose from 16 to 97 microseconds because it now does real work rather than a single multiplication. That is under one percent of the slot it has.

The new row is the one that matters. Week 3 could report that the laptop was late but could not prove the microcontroller never was, because nothing counted it. A counter added this week counts exactly that, and it reads 0 over ten minutes, including throughout the fault-injection campaign in the next section. The two failures the gate's criterion treats as one are now measured apart, and one of them is empty.


## Two faults found while bringing the board up

Neither would have announced itself, and both are worth recording because both would have produced a wrong verdict rather than an obvious failure.

The frame counter tracked one sequence number across all message types, while the control loop and the diagnostics task each run their own counter. Every alternation between them looked like a gap. On a real run it reported 1,566 lost frames on a link that lost none. Gate G3 is stated as zero lost frames, so this counter decides the verdict.

The first connection to the board after a reset always receives nothing, and the second receives the full stream. This cost a long detour, because the symptom looks exactly like firmware that is not running. Opening the port now retries until data arrives, and the retry count is reported so the behaviour stays visible rather than hidden.

The link was also changed to run over the chip's built-in USB port instead of requiring a separate adapter. The design document left the choice between the two open for this gate to settle on measured latency. Both are implemented, so comparing them is a rebuild rather than a rewrite, but only the built-in port can be measured with the hardware currently connected.


# 16. The controller, and how much room it has to improve

Week 7 built the two things a proposed controller has to be measured against: the conventional controller anyone would write, and the theoretical best any controller could achieve. The second one is computed offline by dynamic programming, which searches every combination of decisions across the whole trip. Without it, a claim that a controller saves three percent means nothing, because nobody knows whether three and a half percent or thirty were available.

The answer came back smaller than anyone expected, and it has to be said before the reinforcement-learning work starts rather than after it.


## Consumption on the four standard driving cycles

Watt-hours per kilometre. Lower is better. The last column is how far the conventional controller sits from the theoretical best.

| Cycle | No regeneration | Conventional rules | Theoretical best | Gap |
|---|---|---|---|---|
| WLTC3B | 204.56 | 175.99 | 175.94 | +0.03% |
| UDDS | 207.02 | 167.93 | 167.67 | +0.16% |
| HWFET | 162.26 | 153.90 | 153.89 | +0.01% |
| US06 | 233.14 | 190.47 | 190.39 | +0.04% |

Recovering braking energy is worth a great deal: between 5% on the highway cycle and 23% in city traffic. That is the whole energy story of this vehicle.

Everything after that is not. The theoretically optimal strategy turns out to be a constant instruction -- recover as much braking energy as the battery will accept -- and the conventional controller, which is two thresholds and a taper, is already within a sixth of one percent of it. There is essentially nothing left for a learned controller to find.


## Why this is a property of the problem

It is not a weakness of the search. The controller is split in two on purpose: an inner loop follows the speed profile, and an outer loop manages energy. That split is what makes the energy comparison honest, because it stops a controller from saving energy by driving slower. But it also means the outer loop cannot change how the car drives at all, and once that is fixed:

the discharge power limit can only take away power the speed controller needs, so it is a safety limit and not a lever;

turning the cabin heating down saves energy the same way driving slower does, so it is priced at what it costs and then it is a wash;

recovering braking energy is always better than not, so the best setting is simply the maximum the battery allows.

One lever with an obvious setting and two that do nothing. That is why the optimum is a constant.

There is a direct consequence for one of the planned experiments. Experiment A3 asks whether the controller needs the forecast at all. Under a fixed speed profile the best action does not depend on what happens next, so a forecast cannot help, and A3 can now be predicted rather than run. The design document already accepted that outcome as publishable; what is new is that there is a reason for it rather than a possibility.


## What happens next is the supervisor's decision

This is recorded in the design document as an open item for the supervisor, not resolved here. Three routes:

| Route | What it means | Cost |
|---|---|---|
| Report it | The contribution becomes the embedded engineering plus a negative result: a learned energy manager cannot beat two rules once speed tracking is a hard constraint. The project's stated framing already supports this. | None. Publishable as it stands. |
| Widen the controller's authority | Let the outer loop adjust the target speed inside a tolerance band, with a penalty for arriving late. This is the standard formulation in which a forecast genuinely pays, and it would give A3 something real to measure. | Most work. Changes one of the paper's claims. |
| Make the problem harder honestly | Add battery temperature limits and a battery-ageing cost. Under those, always recovering the maximum stops being optimal. | Moderate. Needs a thermal and ageing model. |

Figure 10. Left: consumption by controller on each cycle. Right: how far each controller sits from the theoretical best, on a log scale. Recovering braking energy is worth tens of percent; everything after that is worth hundredths.

Left panel — what each controller consumes on each cycle. Horizontal axis is the four standard drive cycles, running from stop-start city traffic through steady highway to the deliberately aggressive US06; vertical axis is energy use in watt-hours per kilometre, where lower is better. Five bars per cycle, one per controller. Two of the five are not serious controllers: one throws all braking energy away and one recovers everything it can, and between them they bracket what recovery is worth.

Right panel — the same runs as distance from the theoretical best. Same four cycles; vertical axis is the gap to the offline optimum in percent, on a logarithmic scale. The scale has to be logarithmic because the numbers span from 23 percent down to a hundredth of a percent, and on a normal axis four of the five arms would be a single flat line on zero. The always-regenerate arm is drawn on the floor of the axis because its true gap is exactly zero, which a logarithmic scale cannot show.

Reading it: the left panel's story is the tall bar. Recovering braking energy is worth between 5 percent on the highway and 23 percent in city traffic, and that is the entire energy story of this car. The right panel is the finding that reshaped the project: once regeneration is on at all, everything after it is worth hundredths of a percent, and the hand-written rules sit between 0.01 and 0.16 percent from the theoretical optimum.


## The speed controller holds under disturbance

The energy comparison is only honest if every controller actually follows the driving cycle, so the inner loop was tested with its model deliberately wrong. On a clean run its tracking error is under a millimetre per second, but that number is worthless on its own: the controller's feedforward term is computed from the same vehicle the simulation uses, so it is exact. The table below breaks that arrangement.

| Condition | City cycle error | Aggressive cycle error | Worst instant |
|---|---|---|---|
| nominal | 0.0007 m/s | 0.0013 m/s | 0.017 m/s |
| mass +10% | 0.0183 m/s | 0.0307 m/s | 0.190 m/s |
| drag +30% | 0.0011 m/s | 0.0024 m/s | 0.017 m/s |
| rolling +50% | 0.0020 m/s | 0.0025 m/s | 0.030 m/s |
| grade unknown | 0.0037 m/s | 0.0035 m/s | 0.029 m/s |
| speed noise 0.2 m/s | 0.0219 m/s | 0.0232 m/s | 0.100 m/s |
| link delay 100 ms | 0.0651 m/s | 0.1027 m/s | 0.383 m/s |
| no feedforward | 0.1683 m/s | 0.2952 m/s | 1.499 m/s |

The worst case across every perturbation is 0.30 m/s of average error and 1.5 m/s at its worst instant, on the aggressive cycle with the feedforward term removed entirely. Speed tracking is the constraint the whole energy comparison rests on, and it holds.

One row is a result rather than a check. Injecting realistic speed-sensor noise costs 5.6% of consumption: the controller chases the noise and pays for it in torque reversals. That is a sensor-quality argument with a price attached, and it belongs in the paper.

Figure 11. Speed-tracking error under model error and disturbance, log scale. The clean run at the bottom is the least informative bar in the chart.

Single panel — tracking error under eight different disturbances. Horizontal axis is speed-tracking error in metres per second, on a logarithmic scale because the cases span three orders of magnitude; the vertical axis lists the disturbance applied. Two bars per condition, one for the city cycle and one for the aggressive one. Reading down the list: the clean run; the car 10 percent heavier than the model believes; 30 percent more aerodynamic drag; 50 percent more rolling resistance; a road gradient the model cannot see; noise on the speed sensor; a 100 millisecond delay on the link; and finally the feedforward term removed altogether.

Reading it: the clean run is the least informative bar in the chart, and it is drawn precisely so that it cannot be quoted alone. On a clean run the feedforward is computed from the same vehicle the simulation uses, so it is exact by construction and the resulting sub-millimetre error says nothing about the controller. The worst case across every disturbance is 0.30 metres per second of average error. One bar is a result rather than a check: realistic sensor noise costs 5.6 percent of consumption, because the controller chases the noise.


# 17. The reinforcement-learning ramp-up

Reinforcement learning is the identified skill gap on this project and it is genuinely temperamental, so the schedule spends a week on the setup before the week that needs it to work. That week is done.

Two runs, in this order, because they fail for different reasons and running them together would make a failure impossible to attribute.

| Check | Result | What it tells us |
|---|---|---|
| A textbook problem with a known answer | score -191, target -300 | PASS. The installation and the default settings are sound, so a later failure is the problem and not the tooling. |
| Simulation speed of the real problem | 2649 decisions per second | The simulator is not the bottleneck. |
| Training speed on the real problem | 230 steps per second | Five independent training runs will take 1.8 hours on this laptop. |

The last row is the one that mattered. The design document requires five independent training runs, because a single reinforcement-learning result is not publishable. That requirement is now known to be affordable rather than hoped to be.

After a deliberately short training run the controller already uses 45.5 watt-hours per test episode against the conventional controller's 46.5, but scores slightly worse overall. It is buying that energy by turning the cabin heating down, and the scoring function is charging it for doing so. The scoring function is working.


# 18. What the controller does when something fails

The design document requires that when the slow part of the system misses its deadline, the fast part falls back to simple rules and the event is counted rather than hidden. Week 7 built that, and then broke the system on purpose to check it. A safety path that has never been taken is a claim, not a result.


## Three failures, three different responses

| What goes wrong | How it is noticed | What the controller does |
|---|---|---|
| The energy manager stops answering | its last instruction is more than 300 ms old | the simple rules run inside the fast loop instead |
| The simulation stops sending the car's state | five control periods with nothing received | torque is ramped smoothly to zero and the controller stops acting on a measurement it no longer trusts |
| The prediction takes too long | its own timing exceeds the 40 ms budget | the energy manager uses the simple rules for that step |
| A task stops running altogether | the chip's watchdog timer, 2 seconds | the chip resets, and the reason is reported after the restart |

Treating these as one generic fault is how a controller ends up crawling because a logging task was slow. They are counted separately for the same reason.


## Measured on the board

Two of the three faults have to be injected inside the firmware, because they happen entirely on the chip and cannot be caused from outside it. The third the laptop caused itself, by going quiet for a second.

| Fault injected | What should happen | What did happen |
|---|---|---|
| Laptop silent for 1.0 second | 101 missed states, the first 5 tolerated | 101 missed, 96 ramping down |
| Energy manager stops publishing for 2.0 seconds | 180 control steps on the simple rules | 180 |
| Prediction overruns for 2.0 seconds | 20 missed deadlines and 20 fallbacks | 20 and 20 |
| Control task made to hang | the watchdog resets the chip | task watchdog |

Every count is exactly what the injection schedule implies. During the silent second the commanded torque fell from 226 newton-metres to zero and stayed there: the chip kept sending commands, and what those commands said was that the controller was declining to act on stale information.

Throughout all of it, the number of control loops that missed their own deadline stayed at 0. Handling a failure does not cost the loop its timing.

One of the planned experiments switches this handling off and measures what it was worth. The switch to do that is a compile-time option in the same firmware, so that experiment is a rebuild rather than a reconstruction, and the rebuild has been confirmed to compile. What it is expected to show is worked out in section 19, and what it actually showed, on the board, is section 20.


# 19. What the failure handling is worth, predicted

Nothing in this section was measured. It was written as a simulation on the laptop before any board was attached, and it is reproduced here unchanged, so that the hardware result in section 20 can be read against a prediction that already existed rather than one explained after the fact. Where the two disagree, the measurement is the result and this section is the record of what was expected.

That order is deliberate and the project has already been paid for using it. The offline optimum predicted, with a reason, that the forecast would make no difference to control before any learning run was started, and five training runs then agreed. A prediction produced after a result is worth nothing.


## The question

The previous section built the handling for a missed deadline and triggered it on the board. The obvious follow-up question is what that handling is actually worth, and the way to answer it is to switch it off and measure how much worse things get. That experiment is called A4 and it is the one remaining piece of week 9 that does not depend on any pending decision.

The firmware already has the switch. Turning it off removes exactly two behaviours: the simple rules no longer take over when the energy manager goes quiet, and the torque is no longer ramped down when the car's state stops arriving. Everything else, including noticing and counting the failure, is untouched. That is what makes it a controlled comparison rather than two different experiments.


## What was simulated

The laptop model reproduces the chip's control task step for step, at the same 10 millisecond period, tolerating the same 5 missed updates before it reacts and ramping torque down at the same 10 newton-metres per step.

One detail decides whether the model is honest. When the laptop stops answering, the chip keeps the whole of the last message it received, so it loses not only its speed reading but also the speed it was being asked to reach and the slope of the road. Modelling only the lost speed reading would leave the controller secretly knowing where it was supposed to be going, and would make the failure look milder than it is.

480 paired outages were simulated: four standard driving cycles, 6 outage lengths from 0.2 to 10 seconds, and 20 different starting moments spread across each cycle. The starting moment is varied because a single one can be chosen to flatter either answer: an outage during steady cruising costs almost nothing, and one during hard acceleration costs a great deal.

Each outage is simulated from a 15 second run-up rather than from the start of the cycle, which is what makes 480 runs affordable. The run-up is checked rather than assumed: the worst tracking error anywhere before any outage begins is 0.017 metres per second, so the controller is settled when the failure starts.

Figure 12. Ablation A4 as predicted on the laptop, not measured. Peak speed error against the outage length, with the shipped handling on and with it switched off. Both axes are logarithmic because the error spans four orders of magnitude across the range of outages tried.

Left panel — the ordinary case, and it is the surprising one. Across the middle of the distribution, switching the handling OFF tracks the target speed better at every outage length tried. This is not a fault in the handling. Over a second or two the target speed has barely moved, so simply holding the last command is a better guess than ramping the torque away to nothing.

Right panel — the bad case, where the handling earns its keep. Taking the worst outage out of every set instead of the middle one, the two lines cross. Beyond a five-second outage, holding a stale command produces a larger excursion than ramping down does, because by then the command being held has no relationship to what the car should be doing.


## The predicted numbers

| Outage | Handling on, typical | Handling off, typical | Handling on, worst | Handling off, worst |
|---|---|---|---|---|
| 0.2 s | 0.057 | 0.001 | 0.179 | 0.101 |
| 0.5 s | 0.174 | 0.002 | 0.679 | 0.346 |
| 1 s | 0.363 | 0.031 | 1.499 | 0.612 |
| 2 s | 0.681 | 0.190 | 2.954 | 1.408 |
| 5 s | 1.764 | 0.636 | 6.881 | 8.024 |
| 10 s | 3.392 | 1.437 | 13.265 | 19.705 |

Peak error between the car's speed and the speed it was asked for, in metres per second. Lower is better. Typical is the middle of the 20 starting moments; worst is the worst of them.


## What this means, if it holds

The typical case and the worst case disagree, and that disagreement is the finding rather than a wrinkle in it. This is what a safety mechanism is supposed to look like: it gives up something in ordinary conditions in order to put a limit on how bad the rare case can get.

So the prediction is that A4 will NOT come back empty, and that it will point the opposite way from the obvious reading. Switching the safety handling off should make the typical tracking better, not worse, and the handling only repays its cost in the worst case once an outage lasts about 5 seconds.

Reporting that as the failure handling having turned out to be useless would be a misreading, and it is worth stating plainly in advance because it is the misreading the headline number invites. The handling was never there to improve tracking. It is there so that a controller which has lost contact with the car stops acting confidently on information it knows is stale.


## Two things the prediction rules out

Electrical stress does not distinguish the two. The largest battery current is 158.9 amps with the handling on and 159.2 amps with it off, across every outage length. Any argument that the handling protects the battery should not be made from these numbers.

The absolute error figures are optimistic and should not be quoted on their own. The laptop model computes its feed-forward command from the same vehicle it then simulates, so the model is perfect in a way no real vehicle is, and the feedback term has less work to do than it would on the road. The comparison between the two columns carries over to the hardware; the size of the numbers is a floor.


## What would prove this prediction wrong

Stated now so that the hardware run settles the question instead of being interpreted against it afterwards.

The hardware campaign interrupts the laptop for exactly one second, which is the row this turns on. The prediction for that row is 0.031 metres per second with the handling off against 0.363 with it on, a factor of 12. If the measured error with the handling off comes back larger rather than smaller, the prediction is wrong.

If the count of control loops that miss their own deadline moves away from zero in either build, then the loop is failing to keep its own timing and every comparison above is measuring something else.

The simulated car is noiseless and its timing is exact. The real loop has measured timing jitter and a real serial link, so the measured spread should come out wider than the simulated spread, not narrower. A narrower spread on hardware would mean the simulation is missing something rather than that the hardware is unusually good.


# 20. What the failure handling is worth, measured

This section was measured on the board. The chip ran the control task, the laptop ran the car, and the laptop stopped answering for one second at a time on purpose.


## Why the first attempt did not answer the question

The experiment was run twice, because the first run could not settle what it was for. The harness used to trigger the failure was inherited from the timing work, and it feeds the chip a made-up description of the car computed from a formula rather than from a simulation. The torque the chip asks for never reaches the car that answers it. That was the right choice for measuring timing, because a formula costs the same on every step and so cannot be mistaken for jitter. It is the wrong choice here: if the car does not respond to the chip, then switching the torque off for a second does not slow it down, no error builds up, and the very quantity this experiment exists to measure cannot appear.

The first run is still worth having. It confirms on silicon that the two behaviours really are removed from the build, that the torque is ramped out to zero when the handling is in and held flat when it is not, and that neither version misses its own deadline. What it cannot do is put a number on the cost, so a second harness was written that closes the loop: the validated car model, driven by the torque the chip actually commanded, following a real drive cycle.


## What was measured

Eight one-second outages were injected at eight different points of the US06 drive cycle, first against the firmware with the handling in and then against the firmware with it compiled out, so every outage is a matched pair. The position of the outage is varied rather than fixed because a single choice can flatter either version: an outage while cruising costs almost nothing, and one during hard acceleration costs a great deal. Before each outage the loop was allowed 15 seconds to settle, and the worst error anywhere before any outage was 0.127 metres per second, so the loop was steady each time.

| Outage at, s | Speed, m/s | Worst error on, m/s | Worst error off, m/s | Peak current on, A | Peak current off, A |
|---|---|---|---|---|---|
| 16 | 14.4 | 0.992 | 0.725 | 256 | 147 |
| 99 | 29.8 | 0.343 | 0.034 | 127 | 36 |
| 182 | 24.6 | 0.043 | 0.164 | 69 | 78 |
| 265 | 27.8 | 0.463 | 0.364 | 247 | 217 |
| 347 | 29.7 | 0.142 | 0.086 | 91 | 77 |
| 430 | 30.5 | 0.242 | 0.051 | 112 | 66 |
| 513 | 4.8 | 1.318 | 0.315 | 53 | 55 |
| 596 | 0.0 | 0.002 | 0.002 | 4 | 4 |
| median |  | 0.292 | 0.125 | 101 | 72 |
| worst |  | 1.318 | 0.725 | 256 | 217 |

Table. Each row is one outage, run against both versions of the firmware. Lower is better in every column. MEASURED on the board.

Figure 13. Ablation A4, measured. Left: tracking error, where switching the handling off is better at six of the eight outage positions. Right: peak current while recovering, where switching it off is better at six as well. Blue is the shipped firmware, orange is the firmware with the handling removed.


## The prediction was right about the direction

The prediction in section 19 said that switching the handling off would make typical tracking better, not worse, and that reporting this as the handling being useless would misread a mechanism that was never there to improve tracking. That is what the board shows. Typical worst error is 0.125 metres per second with the handling off against 0.292 with it on. Holding the last command through a short outage is simply a better guess than ramping the torque away, because over one second the target has not moved far.


## And wrong about the size

The predicted gap was a factor of twelve. The measured gap is a factor of 2.3. Almost all of the error is on one side: the prediction for the shipped firmware was close, but it expected the version with the handling removed to hold its speed about four times better than it did. A simulated car is smooth and noiseless, which flatters a strategy whose whole approach is to freeze and wait, and costs nothing to a strategy that ramps to a fixed value. The prediction itself warned that the real spread would be wider than the simulated one, and it is.


## And wrong about the current, for a reason in its own working

The prediction stated that the electrical stress on the battery could not tell the two versions apart, putting them within a third of an amp of each other, and advised against using that argument. On the board they are clearly apart: while recovering from the outage the shipped firmware draws 101 amps at the typical outage against 72 amps with the handling removed.

This is not the simulation disagreeing with the hardware. It is an error in how the prediction measured itself, and it can be seen by reading its code. It took the largest current over the whole simulated run, including the fifteen seconds of ordinary driving before the outage. Those fifteen seconds are identical in both versions by construction, and on a demanding cycle they contain the largest currents of the run, so the number it reported was a property of the warm-up rather than of the failure. The hardware figures above are confined to the recovery window on purpose.


## The longer outage, where the handling earns its keep

The reason the handling is in the firmware at all is the worst case, not the typical one. The prediction has the two versions crossing over at a five-second outage, where holding on to a stale command becomes far worse than ramping the torque away. The same eight outages were repeated at five seconds to test exactly that.

| Outage at, s | Speed, m/s | Worst error on, m/s | Worst error off, m/s | Peak current on, A | Peak current off, A |
|---|---|---|---|---|---|
| 16 | 14.4 | 5.247 | 4.158 | 332 | 207 |
| 98 | 30.3 | 1.461 | 0.442 | 127 | 95 |
| 181 | 25.0 | 0.411 | 1.480 | 265 | 102 |
| 263 | 27.9 | 1.602 | 0.210 | 332 | 77 |
| 345 | 30.1 | 1.220 | 1.714 | 332 | 332 |
| 427 | 30.8 | 1.109 | 0.149 | 332 | 65 |
| 510 | 11.3 | 7.386 | 4.473 | 127 | 110 |
| 592 | 2.8 | 2.105 | 7.949 | 22 | 127 |
| median |  | 1.532 | 1.597 | 298 | 106 |
| worst |  | 7.386 | 7.949 | 332 | 332 |

Table. The same eight outages, lengthened to five seconds. MEASURED on the board.

Figure 14. Ablation A4 at a five-second outage. The worst case now favours the shipped firmware, which is what the handling is for.

The crossover is real, and it is close to where it was predicted. The worst outage of the eight costs 7.39 metres per second with the handling in and 7.95 with it removed; the prediction said 6.88 against 8.02. Both the direction and the size come out close, and this is the prediction's best showing anywhere in the experiment.

The mechanism shows up in a single row. At the outage placed 592 seconds in, the drive cycle is winding down to a stop and the target speed is falling through 2.75 metres per second. Holding on to the last command there means driving five seconds of torque into a car that should be braking, and the version without the handling overshoots by 7.95 metres per second against 2.11 with it. That row is the safety argument in full: the handling is not there because limping tracks well, but because limping fails small where holding on fails large.

Two things changed against the prediction. The typical case is already a tie at five seconds, 1.53 against 1.60 metres per second, where the prediction still had a wide gap in favour of removing the handling. So the ordinary-case cost measured at one second is paid back sooner than expected. And the current drawn while recovering moves sharply the other way: with the handling in it reaches 298 amps at the typical outage against 106, saturating on half the outages tried. Ramping the torque away for five seconds and then catching up is expensive.


## What is still not measured

Two outage lengths are enough to show that the crossover exists and not enough to say where it is. The campaign was later repeated at every whole second from one to five on the current firmware, and section 25 narrows where the worst case changes hands.


# 21. The learned controller, and what it found

Week 8 trained the reinforcement-learning controller the project is named after: five independent training runs, because a single result from a method this temperamental is not publishable, and a matched pair of runs with the forecast removed from what the controller can see. Week 7's offline optimum had already predicted what this would find. The prediction was written down before the runs, and the runs were done anyway, because a predicted result is not a measured one.


## How the arms are compared, and why it matters here

Two numbers are reported for every controller. The raw figure is watt-hours per kilometre as measured. The comparable figure adds back the cabin heating the controller switched off, valued at exactly the energy it saved.

That second column is not bookkeeping. Every trained controller in this table looks better than the conventional one on the raw number and worse on the comparable one, and the whole of the difference is cabin heat. A controller that saves energy by turning the heating down in a Munich winter has done the same thing as one that saves energy by driving slower, and the project rejected that trade in its design document before any of this was measured.

| Controller | Raw Wh/km | Comparable Wh/km | Cabin heat shed | vs conventional |
|---|---|---|---|---|
| Conventional rules | 153.90 | 153.90 | 0.0 Wh | - |
| Learned, with forecast | 151.88 | 154.92 +- 0.78 | 50.2 Wh | +0.66% |
| Learned, forecast removed | 151.74 | 154.68 +- 0.69 | 48.5 Wh | +0.51% |

Five seeds each, 200,000 training steps per seed, evaluated on complete runs of the validation cycle. The test cycle is still sealed. Speed tracking is unchanged across every arm, which is the point of putting tracking in a separate loop the controller cannot touch.


## Ablation A3: does the forecast help?

A3 was the experiment carrying the most risk to the story. It removes the forecast from what the controller can see and changes nothing else.

Difference, forecast minus no forecast: +0.240 Wh/km, with a 95% interval of [-0.669, +1.228].

The interval contains zero. The forecast makes no measurable difference to the controller, which is the result week 7 predicted from the structure of the problem rather than from any property of this particular forecaster: when the speed profile is fixed, the best action does not depend on what happens next, so knowing what happens next cannot help.

This was accepted as publishable in the design document before it was run, and it frees the memory the forecaster occupies. It is a finding about preview horizons in embedded energy management, not a failure of the experiment.

Figure 15. Left: five training runs per arm, each evaluated on complete cycles, against the conventional controller and the offline optimum. Right: where the ten runs finished, with 95% intervals.

Left panel — all ten training runs, evaluated as they learn. Horizontal axis is training steps in thousands; vertical axis is energy on the validation cycle in comparable watt-hours per kilometre, where lower is better. Ten faint lines, five per arm. Every point is a complete run of the validation cycle using the policy as it stood at that moment, not the training reward, because training reward is a different quantity that improves for reasons which do not always mean better driving. The two horizontal reference lines are the hand-written controller and the theoretical optimum, and they sit on top of each other because they are the same number.

Right panel — where all ten runs finished. Two columns, forecast in the controller's state and forecast removed. Five dots per column, one per training run, with a thick bar for the 95 percent confidence interval and a tick at the mean. The same two reference lines carry across, and the ablation result is stated numerically underneath.

Reading it: lower is better, and not one of the ten runs finishes below the two reference lines. Both confidence intervals sit entirely above the hand-written baseline, so the learned controller is not merely no better, it is reliably slightly worse. The two columns overlap almost completely, which is the ablation returning null.


## What this means for the project

Two independent methods now agree. The offline optimum says the best possible policy is a constant instruction, and the learned controller, given five attempts and a third of a million training steps each, does not beat two thresholds and a taper. Neither result depends on the other being right.

That is a finding, and it is the one the paper should lead with in this section. The decision about what to do next -- report it, widen the controller's authority, or make the problem harder honestly -- is section 16's open question and is still the supervisor's to take.


# 22. Putting the learned controller on the chip

A policy that has only ever run in Python is a claim. The trained controller was exported, compiled into the firmware, and run on the board, and its answers were checked against the Python original on the same inputs.

| Check | Result |
|---|---|
| Network shape on the chip | 8-64-64-3, 4,931 numbers |
| Weights on the chip are the weights that were trained | confirmed by checksum |
| Answers match the Python original | worst difference 2.1e-06, tolerance 2e-05 |
| Memory used | 19.3 KB of the 300 KB allowed |
| Time per decision, measured on the chip | 0.121 ms of the 40 ms allowed |

The controller costs 0.3% of the time budget and 6.4% of the memory. It is, in embedded terms, free. The forecaster it consumes is not: that takes 36.46 milliseconds of the same 40.


## The compute estimate was wrong in the other direction

Section 13 reported that dividing a multiply count by a measured multiply rate underestimated the forecaster's real time on the chip by 64%. For this controller the same arithmetic predicts 0.161 milliseconds against 0.121 measured, so it is 25% too pessimistic instead.

The two are not in conflict and the reason is worth a sentence. The forecaster spends much of its time on operations a multiply count cannot see, and it moves more data than fits close to the processor. This controller is a few thousand multiplications on numbers that stay in fast memory, and the chip has hardware that does a multiply and an add together. The estimate is unreliable in both directions and by different amounts, which is a stronger reason to measure than a consistent bias would have been.

The chain from a trained policy to a running one has four links, and each is checked against the one before it. Building that chain found a real fault: the test that compares the C controller against Python was, for a while, compiling the wrong weights and comparing them against themselves. It passed for exactly as long as no policy had been deployed. Section 34 records it.


# 23. What runs on the chip, and what it does there

A decision was taken on what to put on the chip: the learned controller, and no forecaster. The forecast was found to make no measurable difference to the controller, and the forecaster costs 35 of the 40 milliseconds the outer loop is allowed. It cost nearly the whole budget and bought nothing that was being used, so it does not ship.

The version of the controller that ships is the one trained without the forecast, not the one trained with it. That distinction matters more than it looks. Both versions read the same eight inputs; the forecast is two of those inputs rather than extra machinery. Deploying the version trained with the forecast, while providing no forecaster, would feed it two permanently blank inputs it had never seen blank while learning. It would run, and it would return sensible-looking commands, and it would be a controller nobody trained.


## The chip had never actually run either model

This was not a configuration change. Until now the energy manager computed the simple rule-based action on both of its branches, and the slot where the forecaster would go ran a stand-in workload. So no measurement before this one had a learned policy inside the loop.

Four things had to be built. The message the laptop sends was missing one of the eight things the policy looks at, the battery's temperature, which the chip cannot work out for itself. The arithmetic that turns the policy's three outputs into physical commands had to be shipped alongside the policy's weights rather than written into the firmware, because a policy decoded against the wrong limits still produces numbers that look reasonable. Two counters were added so the chip can report how many decisions the policy actually made and how long its slowest one took. And the policy itself had to be wired in, with the old rules kept behind it for when it does not answer in time.


## Ten minutes with the policy in the loop

| Measurement | Value |
|---|---|
| Control loops | 59,650 |
| Decisions the policy made | 5,965 |
| Decisions the old rules had to cover | 0 |
| Loops late against their own deadline | 0 |
| Policy's slowest single decision | 825 us  (0.8% of the time it is allowed) |
| Timing jitter, 99th percentile | 25 us |
| Messages that did not arrive in time | 5 |

Table. The full stack on the chip. MEASURED.

The policy answered every one of the 5,965 decisions asked of it and the old rules never had to step in. Putting a neural network inside the loop moved neither the timing jitter nor the count of loops that missed their own deadline, which stayed at zero.


## The slowest decision is the first one

The policy's slowest single decision took about six times its typical one, and the obvious explanation is that something else on the chip interrupted it. That is not what happened. The figure was identical after one minute and after ten, across roughly six hundred decisions and then six thousand. Being interrupted would almost certainly have produced a worse case somewhere in ten times as many attempts; a first-time cost cannot, because it only happens once, when the code and the weights are read out of storage for the first time after a restart.

So the cost of running the policy has two honest numbers. The first decision after a restart takes about 0.8 milliseconds. Every one after that takes about 0.12. Both are small against the 100 milliseconds the decision is allowed.


## What this does not claim

The learned controller uses more energy than the simple rules it sits in front of: 154.68 watt-hours per kilometre against 153.90, a gap of 0.51%, and the uncertainty around that figure sits entirely on the worse side. Putting it on the chip does not make the car more efficient, and nothing here says it does.

What the deployment shows is a different thing, and it is the one this project set out to show: a learned controller of this size runs inside a real control loop on real hardware, keeps its deadlines, and costs what was measured rather than what was estimated. The energy comparison remains the negative result described in section 16.

One caveat belongs on the record. The slot where the forecaster would have run still executes a stand-in workload, 783 microseconds in this campaign. The forecaster is no longer being deployed, so that work stands in for nothing and the real system has more room than these figures show. It was left alone deliberately: the same stand-in is how the deadline-miss experiments were triggered, and removing it would change the conditions those earlier results were measured under.


# 24. Changing the build toolchain, and re-measuring because of it

The firmware was moved from Espressif's own build system to the Arduino build for the chip, on instruction. The two produce different binaries from the same source, and every number in this report that was measured on the chip had been measured against the old one. None of them could be carried across by argument, so all of them were taken again.

The source code of the control loop did not have to be rewritten. The Arduino build for this chip is built on top of Espressif's, so everything the firmware asks the system for is still there. What changed is how the build is driven, and the compiler settings that come with it, which is exactly what makes timing results non-transferable and is why they were re-run rather than reasoned about.


## Every gate, on both builds

| Measurement | Espressif build | Arduino build | Effect |
|---|---|---|---|
| Gate G1, arithmetic rate | 29.82 million/s | 29.82 million/s | unchanged, PASS |
| Gate G5, forecaster on the chip | 36.46 ms | 35.03 ms | 3.9% faster, fits |
| Gate G3, loop jitter (99th pct) | 25 us | 25 us | identical |
| Gate G3, loops late vs own deadline | 0 | 0 | identical, still zero |
| Gate G3, frames the chip did not get in time | 3 | 9 | worse, still FAIL |
| Controller on the chip | 0.121 ms | 0.123 ms | 1.7% slower |

Table. Every quantity measured on the chip, taken again after the build change. MEASURED, both columns.

No verdict changed and the largest movement in anything measured is 3.9%. The arithmetic rate agrees to four significant figures, which is what should be expected of a tight loop of 8-bit multiplications once both builds use the same optimisation setting, and is now measured rather than assumed. The controller still matches the laptop's arithmetic to six decimal places and still carries the same checksum, so the same weights are running.


## What got worse, and how much it is worth

One quantity moved the wrong way. The number of times the chip did not receive an update in time went from 3 to 9 in 59,650 control loops, and that is the count gate G3 fails on. On the Arduino build it was enough for the car to be eased out of torque once during the ten-minute run.

One run on each build was not enough to tell, so the ten-minute run was repeated 5 times on the Arduino build, with the learned controller in the loop as it ships. The counts were 16, 4, 6, 9, 9: 44 in 298,250 loops, about 8.8 per ten-minute run, with a 95% range of 6.4 to 11.8. Identical runs differ by a factor of 4, so a single run says little.

The earlier Arduino figures sit inside that spread. The single Espressif-build figure of 3 sits below it, but it is one run on older firmware, and the Espressif repeats were not done, so whether the change of toolchain moved the rate is still open. What is now established is the rate of the firmware that ships. Across all 5 runs the loop missed its own deadline 0 times.


## What the new build cannot do

The Arduino build compiles the wireless radios into the program and offers no way to leave them out. Nothing switches them on, and the timing results above show no sign of them. But the reason the old build removed them was that a live radio disturbs both timing and the current drawn from the supply, and only timing was checked here. The current draw was not re-measured on the new build, so that half of the constraint is currently supported by argument rather than by measurement, and is written here as such.


# 25. Where the failure handling starts to pay, measured again

HISTORICAL MEASUREMENT. This sweep used the vehicle model before the power-ceiling correction. Its energy and current-limit interpretation is superseded; corrected-model measurements, when complete, appear in section 28.

Section 20 measured the failure handling at outages of one and five seconds and found that the two versions of the firmware swap places somewhere in between. This section locates that point more closely. The same experiment was run at 0.2, 0.5, one, two, three, four, five and ten seconds.

It was run on the firmware as it is now: built with the Arduino toolchain (section 24) and with the learned controller making the energy decisions (section 23). Neither was true when the earlier points were measured, so every length was measured afresh, including the two that had been measured before, and the earlier figures are not mixed into this table.

| Outage, s | Typical error on, m/s | Typical error off, m/s | Worst error on, m/s | Worst error off, m/s | Outages won: off / on / tie |
|---|---|---|---|---|---|
| 0.2 | 0.037 | 0.026 | 0.096 | 0.150 | 4 / 3 / 1 |
| 0.5 | 0.135 | 0.062 | 0.571 | 0.365 | 6 / 1 / 1 |
| 1 | 0.289 | 0.122 | 1.089 | 0.714 | 6 / 1 / 1 |
| 2 | 0.562 | 0.563 | 3.229 | 1.600 | 5 / 2 / 1 |
| 3 | 0.820 | 0.831 | 5.188 | 2.469 | 6 / 2 / 0 |
| 4 | 1.102 | 1.410 | 6.668 | 3.732 | 5 / 3 / 0 |
| 5 | 1.533 | 1.361 | 7.394 | 7.948 | 5 / 3 / 0 |
| 10 | 3.579 | 4.470 | 13.216 | 24.704 | 4 / 4 / 0 |

Table. Eight outages per length, each run against both versions of the firmware. A tie is a difference under 0.005 metres per second, which only happens with the car standing still. MEASURED on the board.

Figure 16. The failure handling across outage lengths of 0.2 to 10 seconds, on a log axis. Blue is the shipped firmware, orange has the handling removed. The lines only join the measured points; nothing between them was measured.

The worst case swaps between four and five seconds. At four seconds the firmware without the handling still has the smaller worst case, 3.73 metres per second against 6.67. At five seconds the shipped firmware has it, 7.39 against 7.95. That is as closely as the crossover is known. No figure inside that interval was measured, and none is quoted.

At the short end the ordering is the other way round again. At 0.2 seconds the shipped firmware has the smaller worst case, 0.096 metres per second against 0.150. This is not being read as a second crossover. Both figures are small enough to sit inside the spread of eight outages, the difference between them is a few hundredths of a metre per second, and each rests on whichever single outage happened to be worst. The four-to-five second bracket is carried by a mechanism, set out below; this is not.

The typical case tells a quieter story. Removing the handling helps clearly at one second, and from two seconds on the two versions are close. The worst case is where they separate, which is the point of the handling: it is there to stop the rare bad outcome, not to improve the ordinary one.

One thing changed that has nothing to do with the handling. The current drawn from the battery while recovering is much lower than in the earlier runs, and never reaches the limit it hit four times before: at five seconds the shipped firmware's typical figure is 138 amps. The cause is visible before any outage starts. The current during the ordinary driving that precedes each outage, which is identical for both versions, is lower too. So the learned controller, which now sets the power limit, is holding the current down. That limit is not recorded in the result files, so this is the most likely reading rather than a measured one. The handling still costs recovery current at every outage length, as it did before.


# 26. The two controllers across six kinds of driving

WITHDRAWN IN PART. The energy comparison in this section is not valid. The vehicle model let a controller lower its power ceiling and be charged less energy for the same drive, and the learned controller did exactly that. Section 28 gives the evidence and the corrected numbers. The timing results in this section do not depend on the vehicle model and stand as measured. The energy tables are left in place as the record of what was reported.

Every result before this one compares the two energy managers under one set of conditions at a time. This campaign, the processor-in-the-loop or PIL campaign that week 10 of the plan calls for, varies the conditions instead. Six things that a real vehicle meets and a laboratory cycle does not, namely the kind of road, its slope, how full the battery is, how noisy the sensors are, how late the communication link answers and how hard the driver pushes, are each swept across three settings, with both controllers run on the chip against every one of them.

The arrangement is the same as the failure-handling experiment in section 20: the real control software runs on the microcontroller a hundred times a second, and the validated vehicle model runs on the laptop and answers with what the car would do. The difference is what is being asked. That experiment broke the link on purpose and asked what a fault costs. This one leaves everything working and asks what ordinary variation costs.

One thing is varied at a time, so that a number can be attributed to the thing that moved. Energy is reported on the comparable scale used throughout this report: heating the controller chose not to supply is charged back at what it saved, because a controller that turns the heater off is not managing energy, it is just supplying less of it.

| Varied | Setting | Rules: tracking error, m/s | Learned: tracking error, m/s | Rules: energy, Wh/km | Learned: energy, Wh/km |
|---|---|---|---|---|---|
| Driving condition | urban | 0.0118 | 0.0090 | 168.11 | 168.56 |
| Driving condition | highway | 0.0092 | 0.0030 | 154.01 | 154.14 |
| Driving condition | aggressive mixed | 0.0163 | 0.0125 | 190.79 | 176.53 |
| Road grade | uphill | 0.0324 | 0.0092 | 305.14 | 274.20 |
| Road grade | flat | 0.0323 | 0.0127 | 191.16 | 176.77 |
| Road grade | downhill | 0.0183 | 0.0180 | 79.67 | 75.85 |
| Battery state | high | 0.0107 | 0.0114 | 190.66 | 176.52 |
| Battery state | medium | 0.0096 | 0.0145 | 190.61 | 176.33 |
| Battery state | low | 0.0146 | 0.0107 | 190.47 | 176.62 |
| Sensor noise | floor | 0.0290 | 0.0181 | 191.04 | 176.23 |
| Sensor noise | elevated | 0.0465 | 0.0355 | 192.22 | 176.92 |
| Sensor noise | severe | 0.0328 | 0.0297 | 200.65 | 173.17 |
| Communication delay | none | 0.0215 | 0.0256 | 190.88 | 176.47 |
| Communication delay | one period | 35.8338 | 32.8441 | 297.35 | 147.77 |
| Communication delay | three periods | 45.9290 | 45.8463 | 262.80 | 102.68 |
| Driver aggression | normal | 0.0240 | 0.0120 | 190.95 | 176.50 |
| Driver aggression | brisk | 0.0451 | 0.0221 | 196.83 | 168.21 |
| Driver aggression | aggressive | 0.0753 | 0.0901 | 203.26 | 159.34 |

Table. 36 runs on the board, one per cell. Tracking error is the root-mean-square difference between the speed asked for and the speed reached. Energy is on the comparable scale. MEASURED on the board.

Figure 17. Both controllers across every setting, measured on the chip. The upper panel is energy on the comparable scale and the bars can be compared: the scale starts at zero and the differences shown are larger than the repeat spread measured below. The lower panel is tracking error, and its bars cannot: repeats of one setting move that quantity by about as much as the controllers differ, so the panel is there to show that both controllers follow the cycle, not to rank them. Each bar is one run.


## How much a number moves when nothing has changed

The campaign did not plan a repeated measurement, but it contains one. The plain setting, the aggressive cycle on the flat with a full battery and clean sensors, is a level of several of the six things at once, so it was run more than once for each controller, each time with a different draw of sensor noise. Those runs should give the same answer. How far apart they actually land is the smallest difference anything else in this section is allowed to claim.

| Controller | Repeats | Energy mean, Wh/km | Energy spread | Energy spread, % | Tracking mean, m/s | Tracking spread | Tracking spread, % |
|---|---|---|---|---|---|---|---|
| Rules | 5 | 190.96 | 0.13 | 0.07% | 0.0246 | 0.0056 | 22.7% |
| Learned | 5 | 176.50 | 0.17 | 0.10% | 0.0162 | 0.0052 | 32.2% |

Table. Repeats of one identical setting, differing only in the random draw of sensor noise. MEASURED on the board.

The two columns behave completely differently, and the difference decides how the rest of this section may be read. Energy repeats to within 0.10 per cent, so the gap between the two controllers, which is about half a per cent, is several times the measurement's own spread and is a real difference. Tracking error repeats only to within 32 per cent, so two tracking figures in the table that differ by less than that are not distinguishable, and no ordering between them is claimed here however suggestive the table looks. Each cell was run once; this is what one run is worth.

2 of the 18 settings are left out of the comparison that follows, and appear in the table above only. In those the car did not follow the drive cycle at all, with tracking errors in the tens of metres per second against hundredths everywhere else, so the distance it covered is not the distance the cycle asked for and energy per kilometre stops meaning anything. They are the communication-delay settings, and the section below them explains what went wrong there.

The rule for leaving a setting out was chosen after those runs were seen to fail, not before, so it is stated plainly: a setting is excluded when either controller's tracking error exceeds 1 metre per second. Nothing in the campaign lies near that line. The worst included run is 0.090 and the excluded ones are in the tens, so the threshold could be moved by a factor of ten in either direction without changing which settings are dropped.

The learned controller uses more energy than the rules in 2 of the 16 settings and less in 14. Averaged over all of them it uses 8.73 per cent less.

That reverses the result this project has carried since week 8, and the reversal needs explaining rather than announcing.

Section 23 reports the learned controller as 0.51 per cent worse, measured at 154.68 watt-hours per kilometre against 153.90. That measurement was taken on the highway cycle. The project's own plan names the aggressive US06 cycle as the one to report a controller on, and sealed it so that nothing could be tuned against it. It was never spent. This campaign is the first time the two controllers have been compared on it.

The highway row here reproduces the earlier measurement closely: 154.01 watt-hours per kilometre for the rules against the 153.90 measured offline in week 8, a difference of 0.07 per cent, from a simulation on a laptop and a measurement on a microcontroller. So the two results do not conflict. The earlier one is correct about the highway, and the highway is where the two controllers have the least to disagree about.

A word of caution about how much weight this carries. Each setting was run once. The saving is many times the repeat spread measured above, so it is not noise, but a reversal of a headline result deserves a repeat campaign before it is published, and the mechanism below is inferred from the current rather than observed directly. This section reports what was measured; it does not settle what the project should conclude.


## Where the saving appears to come from

The learned controller draws a lower peak current than the rules in 16 of the 16 settings. Losses inside the battery rise with the square of the current, so shaving the peaks saves energy, and it saves more the harder the car is being driven. That is the pattern in the table.

The two ends of it. The hardest setting, sensor noise at severe, peaks at 341 amps for the rules and 292 for the learned controller, and the energy gap there is 13.7 per cent. The gentlest, driving condition at highway, peaks at 104 amps against 95, and the gap is 0.1 per cent.

The likely cause is the discharge power ceiling, one of the three things the energy manager sets. It remains an inference for this campaign: the ceiling the chip applied was not recorded when these runs were taken, only the current that follows from it. Section 25 reached the same explanation from the other direction. The telemetry was added afterwards, so a repeat of this campaign can settle it.

The spread across settings is worth more than the average. The learned controller comes closest to the rules under driver aggression at the aggressive setting (159.34 against 203.26 Wh/km) and is furthest behind under driving condition at the urban setting (168.56 against 168.11 Wh/km).

| Controller | Runs | Control steps | Missed deadlines | Late or lost frames | Worst inference, us |
|---|---|---|---|---|---|
| Rules | 18 | 1,141,416 | 0 | 255,318 | 0 |
| Learned | 18 | 1,141,416 | 0 | 258,585 | 831 |

Table. The timing half of the campaign. A missed deadline is the control loop failing to finish its own work in its ten millisecond slot. Late or lost frames counts the laptop answering late or not at all, which the communication-delay setting causes on purpose. MEASURED on the board.

Across all 2,282,832 control steps of the campaign the loop never missed its own deadline, with the learned controller running inside it and with the link being delayed on purpose. That is the claim this project can make about putting a learned policy in a real-time loop, and the campaign is the widest evidence for it.


## What the communication-delay rows actually show

These rows need reading carefully, because the obvious reading of them is wrong. With a delay of 30 milliseconds the tracking error is 45.9 metres per second, against 0.0215 with no delay. The car is not following the drive cycle at all.

That is not the controller failing. The control loop runs every ten milliseconds, and the delay was added by making the laptop wait before each reply, so the wait is added to the laptop's own work on every single step. At ten milliseconds of delay on a ten millisecond loop the laptop can no longer answer as often as it is asked, and it falls further behind with every step rather than settling one step late. The chip meanwhile met every one of its own deadlines: 0 missed, in 60,001 steps.

So this axis measures how fast the laptop can keep up, not how much delay the controller tolerates. Measuring the second thing needs the delay applied to delivery while the answers keep flowing, which this rig cannot currently do. The rows are reported as measured and the conclusion that the controller is delay-sensitive is not available from them.

What this campaign does not establish. Each cell was run once, so no figure here carries an interval and small differences between two settings are not separable. The three settings of an axis are three points on it, not a characterisation of it. And the vehicle model, though validated against held-out trips earlier in this report, is a model: these are the conditions as the model renders them, not as a road produces them.


# 27. The same campaign, run again on instrumented firmware

WITHDRAWN IN PART. The energy comparison in this section is not valid. The vehicle model let a controller lower its power ceiling and be charged less energy for the same drive, and the learned controller did exactly that. Section 28 gives the evidence and the corrected numbers. The timing results in this section do not depend on the vehicle model and stand as measured. The energy tables are left in place as the record of what was reported.

The previous section reports one run per setting, and its explanation for the energy result rests on a quantity that was not being recorded when those runs were taken. Both of those are weaknesses that a second campaign can remove, so the whole thing was run again after adding the missing measurement to the firmware.

Note what that means for comparing the two. The repeat runs on a build that differs from the first by these counters. Inside each campaign the comparison between the two controllers is clean, because both of its arms share one image. Across the two campaigns the firmware is not identical, so they are shown side by side and never pooled.


## Does it reproduce?

Across the 32 settings where both campaigns tracked the cycle, the energy figures agree to 0.18 per cent on average and 0.71 per cent at worst, the worst being sensor noise at the severe setting for the learned controller. The campaigns ran hours apart, on separately flashed images, with the board reset between every run.

The direction of the headline result is unchanged. In the repeat the learned controller uses less energy than the rules in 14 of the 16 settings, against 14 in the first campaign. Two independent campaigns is not many, and neither is one run per cell within each, but the result is no longer a single measurement.


## The power ceiling, measured rather than inferred

The previous section attributes the energy saving to the discharge power ceiling, and could only infer it from the current that follows from it. The firmware now records the ceiling it applies. This is what it applied.

| Controller | Lowest, kW | Average, kW | Highest, kW |
|---|---|---|---|
| Rules | 40 | 123 | 125 |
| Learned | 40 | 72 | 125 |

Table. The discharge power ceiling the energy manager set, over every setting where the car followed the cycle. MEASURED on the board.

The first thing this settles is a correction. Both controllers use the ceiling, across the same range. An earlier reading of this project held that only the learned one did, and that was wrong.

What separates them is how hard each holds it down through the run: 123 kilowatts on average for the rules against 72 for the learned controller, which is 41 per cent lower. That is a sustained difference rather than a different limit, and it is the quantity that produces the lower peak currents reported in the previous section. The explanation there can now be stated as a measurement.


# 28. Correction: the power ceiling did not slow the car

Each energy manager sends the vehicle model three numbers, and one of them is a ceiling on battery discharge power. Until 6 October 2026 the model applied that ceiling to the power it billed and not to the torque it delivered. A controller that set the ceiling below what the motor was drawing was charged for the ceiling, and the car accelerated as if no ceiling existed.

The table shows it. One fixed ceiling is held for the whole of the aggressive cycle, on the model as it stood and on the model as it stands now.

| Ceiling | Before: energy, Wh/km | Before: tracking error, m/s | After: energy, Wh/km | After: tracking error, m/s | After: distance, km |
|---|---|---|---|---|---|
| 250 kW | 190.39 | 0.0013 | 190.39 | 0.0013 | 12.888 |
| 80 kW | 189.85 | 0.0013 | 190.32 | 0.0106 | 12.888 |
| 60 kW | 187.31 | 0.0013 | 190.31 | 0.0687 | 12.886 |
| 40 kW | 174.85 | 0.0013 | 189.80 | 0.5157 | 12.815 |
| 20 kW | 114.68 | 0.0013 | 180.57 | 2.9224 | 11.845 |
| 5 kW | 8.05 | 0.0013 | 156.16 | 16.1464 | 4.453 |

Table. A constant power ceiling on US06, regeneration fully on. SIMULATED on the laptop. The "before" columns run the vehicle model from the commit preceding the fix, read out of the repository history by scripts/run_plant_correction.py.

Figure 18. One fixed power ceiling on US06, before the fix in orange and after it in blue. Before, a lower ceiling reduced the energy billed and left tracking and distance untouched. After, it costs both. The horizontal axis is not to scale. SIMULATED.

On the old model the lowest ceiling drove the same 12.89 kilometres with the same tracking error for 8.05 watt-hours per kilometre, against 190.39 with the ceiling open. That is not an efficient drive. It is a bill that stopped counting.


## Why this was the week-10 result

The learned controller may set the ceiling anywhere from 40 to 125 kilowatts. On the old model it scores 176.71 watt-hours per kilometre on US06 against 190.47 for the rules, and a ceiling pinned at 40 kilowatts scores 174.85. The campaign on the chip measured the same gap. Three features of that campaign's own tables pointed here and were read as something else.

The learned controller finished below the offline optimum of section 16 at equal tracking error. An optimum is not beaten by seven per cent.

Its advantage grew with how hard the car was driven, on three separate axes. Harder driving is where a ceiling binds for longest.

The advantage vanished on the highway and urban cycles, where demand stays under the 40 kilowatt floor and no ceiling can bind.

The earlier explanation, that the learned controller saves energy by shaving current peaks, was labelled as inferred. It was wrong.


## The fix

The motor now receives what the battery delivered, less the auxiliary load, and acceleration is computed from the torque that power can produce, and the pack's current limit is treated the same way because it had the same fault. Nothing else changed. A limit that does not bind leaves every output bit for bit as it was, and a test asserts that.


## Both controllers on the corrected model

| Cycle | Model | Rules, Wh/km | Learned, Wh/km | Learned vs rules | Rules: tracking, m/s | Learned: tracking, m/s |
|---|---|---|---|---|---|---|
| WLTC3B | before | 175.99 | 175.78 | -0.12% | 0.0006 | 0.0006 |
| WLTC3B | after | 175.99 | 176.53 | +0.31% | 0.0006 | 0.0286 |
| UDDS | before | 167.93 | 168.31 | +0.23% | 0.0007 | 0.0007 |
| UDDS | after | 167.93 | 168.32 | +0.23% | 0.0007 | 0.0007 |
| HWFET | before | 153.90 | 154.07 | +0.11% | 0.0003 | 0.0003 |
| HWFET | after | 153.90 | 154.07 | +0.11% | 0.0003 | 0.0003 |
| US06 | before | 190.47 | 176.71 | -7.22% | 0.0013 | 0.0013 |
| US06 | after | 190.47 | 190.71 | +0.13% | 0.0013 | 0.4815 |

Table. The rule manager and the learned controller exported before retraining, before and after the fix. SIMULATED on the laptop. This snapshot is not the retrained policy.

The rules barely move: 190.47 before, 190.47 after. Their ceiling sits near 125 kilowatts and almost never binds. The deployed learned controller goes from 176.71 to 190.71, and its tracking error on US06 rises from 0.0013 to 0.4815 metres per second, with a worst lag of 3.65. It was trained on a model that paid it to lower the ceiling, and on a model that does not, the habit only costs it speed.


## Retraining on the corrected vehicle model

| Controller | Mean, Wh/km | Seed SD, Wh/km | 95% interval, Wh/km | Against rules |
|---|---|---|---|---|
| Rule manager | 153.90 |  |  |  |
| without forecast | 154.86 | 0.51 | 154.48 to 155.28 | +0.62% |
| with forecast | 155.12 | 0.82 | 154.51 to 155.73 | +0.79% |

Table. SIMULATED on HWFET, the validation cycle, with 5 training seeds per learned arm. Shed cabin heat is charged back. These values come from docs/week11-sac-corrected.json.

The no-forecast seed selected on validation is seed 3, at 154.21 watt-hours per kilometre. It was exported for the corrected board campaign. Selection used validation rather than US06. Exporting weights is not a board measurement.

The paired forecast difference is +0.262 watt-hours per kilometre, with a 95% interval from -0.698 to +0.982. The interval includes zero, so this retraining does not show a forecast benefit.


## Link outages on the corrected model

| Outage, s | Median on, m/s | Median off, m/s | Worst on, m/s | Worst off, m/s | Late on | Late off |
|---|---|---|---|---|---|---|
| 0.2 | 0.060 | 0.059 | 0.228 | 0.182 | 0 | 0 |
| 0.5 | 0.171 | 0.103 | 0.571 | 0.202 | 0 | 0 |
| 1 | 0.353 | 0.157 | 1.341 | 0.370 | 0 | 0 |
| 2 | 0.674 | 0.496 | 3.203 | 1.486 | 0 | 0 |
| 3 | 0.915 | 0.812 | 5.189 | 1.408 | 0 | 0 |
| 4 | 1.211 | 1.548 | 6.670 | 3.727 | 0 | 0 |
| 5 | 1.638 | 1.440 | 7.396 | 7.971 | 0 | 0 |
| 10 | 3.715 | 5.328 | 13.275 | 18.187 | 0 | 0 |

Table. MEASURED on the board with the retrained actor and corrected host plant. Each duration has eight paired onsets. Handling-on and handling-off files remain separate from the historical sweep.

Counter checks: all sixteen files passed.

Figure 19. Corrected-model A4 sweep from 0.2 to 10 seconds. MEASURED on the board. Lines join measured points only.


## What stands and what does not

Withdrawn: the statement that the learned controller uses less energy than the rules in 14 of 16 settings, and its repeat.

Unaffected: every timing result. Missed deadlines, inference time and jitter are measured on the chip and do not pass through the energy bookkeeping.

Unaffected: the offline optimum and the highway comparison of section 21. No ceiling bound in either.

Re-measured above: the learned-controller runs of the failure-handling sweep in section 25, where the ceiling also bound.


## The campaign again, on the corrected model

| Varied | Setting | Rules: tracking error, m/s | Learned: tracking error, m/s | Rules: energy, Wh/km | Learned: energy, Wh/km | Learned vs rules |
|---|---|---|---|---|---|---|
| Driving condition | urban | 0.0131 | 0.0156 | 168.13 | 169.30 | +0.70% |
| Driving condition | highway | 0.0036 | 0.0035 | 153.96 | 154.40 | +0.29% |
| Driving condition | aggressive mixed | 0.0436 | 0.2262 | 191.41 | 191.48 | +0.03% |
| Road grade | uphill | 0.0390 | 0.2366 | 305.26 | 305.21 | -0.02% |
| Road grade | flat | 0.0150 | 0.2287 | 190.75 | 191.43 | +0.36% |
| Road grade | downhill | 0.0101 | 0.1931 | 79.30 | 83.83 | +5.71% |
| Battery state | high | 0.0263 | 0.2332 | 190.93 | 191.37 | +0.23% |
| Battery state | medium | 0.0265 | 0.1955 | 191.00 | 191.63 | +0.33% |
| Battery state | low | 0.0206 | 0.1678 | 190.80 | 191.20 | +0.21% |
| Sensor noise | floor | 0.0205 | 0.2295 | 190.75 | 191.81 | +0.55% |
| Sensor noise | elevated | 0.0145 | 0.2175 | 191.33 | 192.90 | +0.82% |
| Sensor noise | severe | 0.0548 | 0.1921 | 201.55 | 210.53 | +4.45% |
| Communication delay | none | 0.0144 | 0.2299 | 190.73 | 191.76 | +0.54% |
| Communication delay | one period | 31.4772 | 25.6688 | 349.52 | 378.26 | +8.22% |
| Communication delay | three periods | 43.3592 | 30.3715 | 359.78 | 339.20 | -5.72% |
| Driver aggression | normal | 0.0276 | 0.2281 | 190.99 | 191.98 | +0.52% |
| Driver aggression | brisk | 0.0450 | 0.3306 | 197.16 | 197.38 | +0.11% |
| Driver aggression | aggressive | 0.0981 | 0.5042 | 204.46 | 204.75 | +0.14% |

Table. 36 runs on the board against the corrected vehicle model, one per cell. 2,282,832 control steps, 0 of them late. MEASURED on the board.

In the 16 settings where both controllers followed the cycle to within one metre per second, the learned controller used less energy in 1.

The mean paired energy difference across valid settings is +0.935%, learned against rules. Each setting has one run per controller; the settings are not repeated samples of one condition.

Excluded from energy aggregates: 2 settings where one controller's tracking RMSE reaches one metre per second. The serialized link-delay axis measures host throughput rather than independent link latency; its rows remain visible.

Figure 20. Corrected-model campaign: comparable energy beside tracking error. MEASURED on the board, one run per cell.


# 29. Sensor noise and the speed loop, measured on the board

Week 7's robustness test found that speed-sensor noise costs energy because the speed controller chases the noise and pays for it in torque reversals, and section 26 saw the rule manager's consumption rise with noise on the chip. Both were observations about a loss. This section measures the loss on the board and what removes it.

The loss is in the speed loop and not in the energy manager. In simulation a constant energy instruction loses as much as the rule manager does under the same noise. The loop acts on every sample, so a noisy reading makes it drive and brake by turns, and the round trip through the motor and the battery is paid for.

Three versions of the firmware were run, all with the rule manager deciding energy, differing only in what the speed loop is given to control on.

| Version | What the speed loop controls on |
|---|---|
| Shipped | The speed measurement as it arrives |
| Filter | A Kalman estimate: it predicts the speed from the torque it commanded, corrects with the measurement, and learns how noisy the measurement is and how far the car departs from its model |
| Filter and detector | The same, with a check on top that the speed reading agrees with the measured acceleration. If it does not, the reading is set aside and the loop runs on acceleration alone until it does |


## Energy

| Setting | Shipped, Wh/km | Filter, Wh/km | Filter and detector, Wh/km |
|---|---|---|---|
| Urban, noise floor | 168.10 | 168.05 | 167.99 |
| Highway, noise floor | 153.98 | 153.92 | 153.92 |
| Aggressive (US06), noise floor | 190.79 | 190.61 | 190.59 |
| US06, noise floor, second seed | 190.98 | 190.56 | 190.63 |
| US06, 3 times the noise | 191.27 | 190.67 | 190.54 |
| US06, 10 times the noise | 200.42 | 190.80 | 190.79 |

Table. Energy on the comparable scale. One run per cell, each on the firmware version its column names, confirmed from the chip's own report. MEASURED on the board.

Ten times the sensor noise costs the shipped loop 9.44 watt-hours per kilometre, 4.9 per cent. With the filter it costs 0.24, and with the detector added 0.16. The whole of the loss is recovered.

At ordinary noise the three versions are within 0.10 per cent of one another on every cycle. The shipped loop's own two runs of the same setting differ by 0.10 per cent, so no saving is claimed there.


## Peak battery current and tracking

| Setting | Shipped | Filter | Filter and detector |
|---|---|---|---|
| Urban, noise floor | 118 A, 0.0104 m/s | 111 A, 0.0193 m/s | 110 A, 0.0119 m/s |
| Highway, noise floor | 97 A, 0.0055 m/s | 92 A, 0.0035 m/s | 92 A, 0.0031 m/s |
| Aggressive (US06), noise floor | 284 A, 0.0161 m/s | 262 A, 0.0112 m/s | 261 A, 0.0103 m/s |
| US06, noise floor, second seed | 295 A, 0.0271 m/s | 260 A, 0.0086 m/s | 263 A, 0.0144 m/s |
| US06, 3 times the noise | 330 A, 0.0124 m/s | 273 A, 0.0163 m/s | 265 A, 0.0095 m/s |
| US06, 10 times the noise | 341 A, 0.0257 m/s | 288 A, 0.0249 m/s | 286 A, 0.0254 m/s |

Table. Peak battery current, then tracking error (root-mean-square). MEASURED on the board.

Under ten times the noise the shipped loop's peak current reaches 341 amps. The filter holds it at 288.

Tracking error is under 0.03 metres per second everywhere, and this table cannot rank the versions more finely than that. The shipped loop's two runs of one setting read 0.0161 and 0.0271.


## What it costs on the chip

The longest the control computation took was 62 microseconds as shipped, 69 with the filter and 73 with the detector, of a 10,000 microsecond period. No control step was late in any run.


## The detector on a healthy sensor

No fault was injected in this campaign, so it says nothing about whether the detector catches one. What it measures is the opposite error. In 1.26 hours the detector raised its flag 1 time on a sensor with nothing wrong with it, in the urban run, and dropped it again after 50 control steps, the shortest its own rule allows. In simulation it raised none in 3.8 hours.

The firmware was then made to report which of the detector's tests raised the flag and when, and the clean cycles were run twice more. The alarm came back both times in the same place, 1255 seconds into the urban cycle with the car creeping at 0.45 metres per second, and it comes back on the same step when the run is replayed on the laptop with a copy of the control task in place of the board. So it is not the link or the chip. It recurs because each setting uses one fixed noise seed: this is one event seen four times.

The replay shows the true speed, which the board cannot. Nothing was wrong with the sensor. The speed the detector works out from acceleration had drifted 0.018 metres per second low, and the noise on the speed reading happened to average 0.013 high over the same fifth of a second. The detector's threshold allows for the second kind of error and not the first, which is typically 0.005 metres per second and reached 0.022 in this run. The threshold is where the fault lies. One such event in about five hours of distinct clean driving, simulated and measured together, is all the evidence there is on how often.


## The detector against a real acceleration channel

The detector trusts measured acceleration. In simulation and on the board that channel is the car's true acceleration with random noise on it. The BMW i3 archive logs an acceleration channel beside speed, so the assumption could be checked against a real one: 70 trips, 30 hours, with no sensor fault in them.

It does not hold. The detector would be flagged 99 per cent of the time, on every trip. The two logged channels agree well from one sample to the next, but differ by a slow component of about 0.11 metres per second squared. The detector integrates acceleration over about two seconds, which turns that into a standing gap of about 0.22 metres per second, against a fault threshold of 0.036. Random noise averages away in that integral and a slow error does not, which is why the simulation never showed it.

So the detector's results above and in simulation hold for the acceleration channel they were given, and not for one like this. It would need its threshold set from the measured disagreement, and would then no longer separate a small offset from healthy driving. That redesign has not been done. The filter does not use the acceleration channel and is not affected. The logs are sampled ten times a second and the firmware runs at a hundred, so the share of time flagged is indicative; the size of the standing gap does not depend on the rate.


## Against the criteria

The criteria were fixed in the design before any of this was built, and the script that applies them was committed before the runs finished.

| Criterion | Filter | Filter and detector |
|---|---|---|
| Clean energy within 0.2% of the shipped loop | pass | pass |
| Clean tracking within 0.005 m/s of the shipped loop | FAIL | pass |
| At least half of the 10x noise loss recovered | pass | pass |
| Tracking under 0.1 m/s in every run | pass | pass |
| No late control step | pass | pass |
| No false alarm on a healthy sensor | not applicable | FAIL |

The filter's failure is on the urban cycle: 0.0193 against 0.0104, 0.0089 apart where the bound is 0.005. On the other two cycles it tracks better than the shipped loop. The gap is smaller than the 0.011 by which the shipped loop differs from itself, so the bound asks for more than one run per cell can show. It stays a failure because the bound came first.


## What this does not cover

Sensor faults. A stuck, dropped or offset speed reading had been tested in simulation only when this campaign was run. Section 30 puts them on the board.

Twenty-five times the noise, and noise that changes during a drive.

A car heavier than the model the filter carries.

Repeats. Each cell is one run.


# 30. A fault checker that works on the board

The car's controller needs to know its speed. If the speed sensor freezes, drops to zero or starts reading a little wrong, the controller acts on a false number. A fault checker watches for this. When it raises the alarm, the controller stops trusting the sensor and works out the speed another way until the sensor behaves again.

Section 29 ended with the first checker not usable. It compared the speed reading with the acceleration reading, and it had only ever been tested against a perfect acceleration signal with a little random noise. A real acceleration signal also drifts slowly. Week 13 added that drift to the simulation, sized from 19 logged BMW i3 trips.

With the drift added, the first checker failed in 5 of the 7 test conditions. It raised the alarm on a healthy sensor for most of the drive. SIMULATED.


## The new checker

The new checker makes three changes. It estimates the slow drift in the acceleration signal and removes it. It looks for a sudden jump in the speed reading, which a fault produces and a slow drift does not. And it allows for its own uncertainty before raising the alarm.

In simulation it raised no false alarm on a healthy sensor in any condition, and caught 551 of 560 faults within half a second on the highway cycle and 533 of 560 on the aggressive cycle. The ones it caught late were all the same kind: a small error of half a metre per second while the sensor was ten times noisier than normal. SIMULATED.


## Measured on the board

No fault had been put on the board before this week. The new checker was written again in C for the chip and compared with the laptop version on 4,000 samples, step by step, until the two agreed on every step. Then three versions of the firmware were run on the board. Each was given the same 40 faults on the aggressive cycle and two clean ten-minute drives. The laptop played the car and injected the faults; the checker ran on the chip.

|  | First checker | New checker | New checker with rule helper |
|---|---|---|---|
| Faults caught within half a second | 33 of 40 | 40 of 40 | 40 of 40 |
| Slowest catch, seconds | 5.18 | 0.32 | 0.32 |
| False alarms before any fault | 220 | 0 | 0 |
| False alarms on two clean drives | 162 | 0 | 0 |
| Still raising the alarm when the run ended | 21 | 0 | 0 |
| Largest speed error during a fault, m/s | 1.93 | 0.67 | 0.61 |
| Typical speed error during a fault, m/s | 0.79 | 0.25 | 0.20 |
| Control steps finished late | 0 | 0 | 0 |
| Longest control calculation, millionths of a second | 72 | 74 | 78 |

Table. Injected speed-sensor faults on the board. One run per case, each on the firmware its column names, confirmed from the chip's own report. MEASURED on the board.

The new checker caught all 40 faults, the slowest in 0.32 seconds, and raised no false alarm. The first checker caught 33 and raised 162 false alarms on one clean drive with a drifting acceleration signal. That is the failure the simulation predicted, now seen on the chip.

The cost is small. The new checker's longest control calculation was 74 millionths of a second against 72 for the first, out of the 10,000 available, and no control step finished late in any run.

The rule helper in the last column is explained in the next section. In this single run it looked slightly better than the checker alone. The runs were repeated in week 14 with other draws of noise, and the difference did not hold: section 33.


## What this does not cover

A real acceleration sensor. The drift on the board was simulated from what the logged trips showed.

Repeats. Each case was run once, with one draw of noise.

The new checker has not passed every limit set in advance. In simulation it is still late on a few small errors under heavy noise. On the board those cases were caught in 0.22 to 0.32 seconds.


# 31. AI helpers around the fault checker

The fault checker makes fast decisions, one every hundredth of a second. The plan proposed a second, slower layer: a helper that looks back over the last tenth of a second and advises the checker. The helper may only do four things: keep an alarm raised, release it, choose which backup speed to use, or make the checker more watchful. It never commands the motor.

The plan intended this seat for Jev, a paid online AI model. Jev has not been purchased, so no result in this report is a Jev result. To test the idea itself, three other helpers were put in the same seat: a helper made of hand-written rules, and two small neural networks of 1,508 and 550 numbers, small enough for the chip.


## As judges, the AI helpers were better

Each helper was first scored on its diagnosis alone, without letting it change anything. While an alarm was raised, the rule helper recognised a real fault 94% of the time and the larger neural network 99%. With no alarm raised, the rule helper recognised 1% of faults and the network 88%. SIMULATED, 540,960 tenth-of-a-second blocks from the highway cycle.


## In control of the car, they were worse

|  | Largest speed error, highway, m/s | Largest speed error, aggressive, m/s | False alarms, highway | False alarms, aggressive |
|---|---|---|---|---|
| New checker alone | 3.7 | 5.1 | 0 | 0 |
| With the rule helper | 1.2 | 1.4 | 0 | 0 |
| With the larger neural network | 9.7 | 10.8 | 4 | 3 |
| With the smaller neural network | 3.0 | 12.8 | 2 | 5 |

Table. Each helper on the chip, with no delay. Largest speed error through any of 560 faults; false alarms on the clean drives. SIMULATED on the laptop.

The rule helper cut the largest speed error from 3.7 to 1.2 metres per second on the highway cycle, with no false alarm. The neural networks, which judged faults better, drove the car worse: up to 13 metres per second off on the aggressive cycle, and they added false alarms.

The cause was traced on the highway cycle. The networks were right that the sensor was faulty, so they kept the alarm raised. While the alarm is raised the controller works out its speed from a backup, and both backups drift. For a small sensor error, five seconds on a drifting backup did more harm than trusting the slightly wrong sensor would have. A better judge does not fix a drifting backup.


## Delay, and what it means for an online helper

An online helper answers late. The rule helper was tested with its answers delayed. Up to half a second it worked about as well as with no delay. At one second its advice arrived too late to be used, and the result was the checker alone. A lost connection during a fault also left the checker working alone, which is the designed behaviour.


## Mixing the two backup speeds did not help

One further idea was tried: instead of choosing one backup speed, use a mix of the two, with the mix set by a fixed number or by a helper. No mix beat the rule helper's simple choice. A fixed half-and-half mix gave a largest error of 8.0 metres per second on the aggressive cycle. SIMULATED.


## What this means for buying Jev

For the sensor-fault task, the evidence is against it. The simple rules did the job, and the limit was the drifting backup speed, which no helper can fix by judging better.

A hosted helper would need to answer within about half a second and bring information the car does not already have.

Nothing here tests Jev itself. Its seat in the software is ready if it is bought later.


# 32. Planning the speed to save energy

Everything before this section followed a speed trace that was handed to the controller. This section asks a different question: if the car may choose its own speed, how much energy can it save? This is a new task. It does not change any energy figure earlier in the report.

The rules were fixed before any planner was run. A route is a standard drive with the driver taken out. The planner must cover the same distance, make every stop and wait the same time at each, stay under the fastest speed the drive reached nearby, accelerate and brake no harder than the drive did, and arrive at the same time within 1%.

One thing is missing from this task, and it limits what the numbers mean: other traffic. Where the recorded drive slowed for a car ahead, the planner is free not to. The savings below are for an empty road. They are the most that planning could give, not what it would give in traffic.

|  | Aggressive route, Wh/km | Saving | Highway route, Wh/km | Saving |
|---|---|---|---|---|
| The drive as recorded | 190.5 | 0.0% | 153.9 | 0.0% |
| Planner that sees the whole route | 170.6 | 10.4% | 152.1 | 1.2% |
| Planner that sees 300 m ahead | 172.4 | 9.5% | 152.7 | 0.8% |
| 300 m ahead, with a learned estimate of the rest | 170.6 | 10.4% | 152.3 | 1.1% |
| Neural network that picks the speed directly | 190.4 | 0.0% | 153.4 | 0.3% |

Table. Energy on the comparable scale, each speed plan driven through the full vehicle model with the speed controller and the rule energy manager. No other traffic. One run, reported as it came out. SIMULATED on the laptop.

On the aggressive route the planner used 10.4% less energy than the recorded drive, with the same stops and the same arrival time. On the steady highway route it saved 1.2%: that drive had little to smooth out.

A planner that sees only 300 metres ahead saved 9.5%. Giving it a small neural network that estimates the cost of the rest of the route brought it back to 10.4%. This is the one place in the project where a learned part clearly earned its keep.

A neural network asked to pick the speed directly, with no planning behind it, saved 0.0% on the aggressive route. It kept every rule, because a simple arithmetic check forces it to, but it drove no better than the recorded driver.

The planners draw a higher peak battery current than the recorded drive, 319 to 340 amperes against 257 on the aggressive route. Energy fell and peak current rose. The task set no current limit, and the cause was not examined.


## What this does not cover

Other traffic, traffic lights, hills.

The board. No planner was run on the chip.

Repeats. One training run, one test route.

Sending plans from a remote computer. It was considered and not run: the local planner already recovers the full saving, so a remote one would add a link without adding a result.


# 33. Week 14: board repeats, a steadier backup speed, and traffic

Week 14 followed up three things that sections 30 to 32 left open: each board case had been run only once; the backup speed used while an alarm is raised drifts; and the speed planner had an empty road.


## The board runs, repeated

The same 42 cases per version were run twice more on the board, each time with a different draw of sensor noise and of acceleration drift. With the first run that makes 120 injected faults and 1 hour of clean driving for each version.

|  | New checker | New checker with rule helper |
|---|---|---|
| Faults caught within half a second | 120 of 120 | 120 of 120 |
| Slowest catch, seconds | 0.32 | 0.33 |
| False alarms in one clean hour | 0 | 0 |
| Alarm dropped while the fault was still there | 47 | 30 |
| Still raising the alarm when the run ended | 0 | 3 |
| Largest speed error during a fault, m/s | 0.83 | 1.32 |
| Typical speed error during a fault, m/s | 0.43 | 0.40 |
| Control steps finished late | 0 | 0 |

Table. Injected speed-sensor faults on the board, three draws of noise pooled. Cases that lost more than 16 frames were set aside and run again. MEASURED on the board.

The new checker's result holds. All 120 faults were caught, the slowest in 0.32 seconds, with no false alarm and no late control step.

The rule helper's advantage on the board does not hold. In the first run its largest speed error was 0.61 metres per second, a little under the checker alone. Over three draws it is 1.32 against 0.83, and it left 3 alarms raised at the end of a run where the checker alone left none. It does drop the alarm early less often (30 against 47). The rule helper helps in simulation. On the chip it has not been shown to.


## A backup speed that does not drift

Section 31 found what limits every helper: while the sensor is distrusted the controller works from a backup speed, and both backups drift. One comes from the acceleration reading and drifts with that reading's error. The other is the vehicle model's prediction and drifts with whatever the model has wrong.

The fused backup speed is one calculation that keeps track of three things: the speed, the model's error and the acceleration reading's error. While the sensor is trusted it learns both errors. While the sensor is distrusted it carries on with what it learned. The checker itself is unchanged. Its three settings were chosen on the urban training cycle only.

| Highway cycle | Largest speed error, m/s | Typical speed error, m/s | Alarms stuck | Clean false alarms |
|---|---|---|---|---|
| New checker alone | 3.74 | 0.56 | 14 | 0 |
| New checker with the rule helper | 1.24 | 0.24 | 10 | 0 |
| With the fused backup speed | 0.62 | 0.08 | 0 | 0 |
| Fused backup speed and rule helper | 0.70 | 0.09 | 10 | 0 |

| Aggressive cycle | Largest speed error, m/s | Typical speed error, m/s | Alarms stuck | Clean false alarms |
|---|---|---|---|---|
| New checker alone | 5.10 | 0.58 | 32 | 0 |
| New checker with the rule helper | 1.41 | 0.47 | 5 | 0 |
| With the fused backup speed | 2.59 | 0.55 | 2 | 0 |
| Fused backup speed and rule helper | 1.29 | 0.50 | 4 | 0 |

Tables. Largest speed error through any of 560 faults, and the typical error in the hardest condition. SIMULATED on the laptop.

On the highway cycle the fused backup speed is the best result so far: largest error 0.62 metres per second against 3.74 for the checker alone and 1.24 with the rule helper, and no alarm left stuck.

On the aggressive cycle it is the best in 6 of the 7 conditions, with a largest error of 0.61 to 0.64. It is the worst in the remaining one: a car 10% heavier than the model, 2.59. That is where the model is most wrong and changes fastest. The settings were chosen on gentle urban driving, which is the likely cause; it was not tested.


## Speed planning with traffic

Section 32 let the planner drive an empty road. A real car is in traffic. Here the planner must stay within a set distance of the recorded drive at every second, ahead or behind. Distance covered and arrival time are the recorded drive's exactly.

| The car stays | Aggressive route, Wh/km | Saving | Highway route, Wh/km | Saving |
|---|---|---|---|---|
| The recorded drive | 190.5 |  | 153.9 |  |
| Within 5 m | 186.0 | 2.3% | 154.0 | -0.1% |
| Within 10 m | 184.0 | 3.4% | 153.4 | 0.3% |
| Within 25 m | 180.7 | 5.1% | 152.6 | 0.8% |
| Within 50 m | 176.7 | 7.2% | 151.9 | 1.3% |
| Within 100 m | 172.0 | 9.7% | 151.6 | 1.5% |
| Within 200 m | 166.6 | 12.6% | 151.3 | 1.7% |

Table. Energy on the comparable scale, each plan driven through the full vehicle model. One run per distance. SIMULATED on the laptop.

About half of the empty-road saving survives a tight limit. Held within 25 metres of the recorded drive the planner still saves 5.1% on the aggressive route, and within 100 metres 9.7%. On the steady highway route there is little to save at any distance.


## What this does not cover

A real acceleration sensor. The drift on the board is still simulated.

The fused backup speed on the board. It exists on the laptop only.

A traffic model. The traffic here is one recorded drive.

Jev. It was not purchased and is not tested.


# 34. Results that went against expectation

Each one is reported because each one changes what the paper may claim, and a supervisor reading the work will find them more convincing than the successes.


## The learned controller loses to two thresholds

Five independent training runs, and every one of them finishes worse than a controller that is two thresholds and a taper, once the cabin heating they switched off is charged back. The offline optimum predicted it and the training measured it, and the two do not depend on each other. Section 21.


## The forecast makes no difference to the controller

Removing it changes the result by an amount whose confidence interval contains zero, and whose sign is not consistent across the five runs. This was accepted as publishable in the design document before it was run, and week 7 gave it a reason rather than leaving it a possibility.


## A parity test was passing without testing anything

The test that compares the controller written in C against the same controller in Python was, for a while, compiling one set of weights and comparing them against another network's expected answers. The cause is a C rule: an include written with quotes is resolved against the including file's own directory before any search path, so the file under test kept finding the deployed weights whatever the test asked for. It passed honestly for exactly as long as nothing had been deployed. Two fixes: the include now searches the path only, and the weights carry a checksum that the inference code itself reports, because two policies of the same shape are indistinguishable without one.


## A model 27 times bigger is not better

The last piece of the 8-bit experiment trained a deliberately oversized model to teach the small one. The teaching changed nothing measurable, and the reason is that the big model was not better than the small one to begin with: 27 times the parameters, and slightly worse. Every model tried falls within 0.89% of the others, which is less than what converting to 8-bit costs. Section 14.


## The energy-management problem has almost no room in it

The theoretically optimal strategy is a constant instruction, and two thresholds get within a sixth of a percent of it. This is the largest of these findings and it is the subject of section 16, including the three routes open and the fact that choosing between them is the supervisor's decision rather than one taken here.


## The fitted rolling resistance is not a rolling resistance

It is 2.2 times larger than an independent measurement on a comparable car. It is a lumped loss term named after the physics it stands in for rather than the physics it contains. The parameter file now says so and an automated test fails if that statement is removed.


## Gate G4 was already passed before the models existed

A linear regression beat the naive baseline by 14.5% against a required 10%. The gate as written could not distinguish a Transformer from a matrix calculation, so every model is now reported against the regression too.


## Physics-informing does not improve accuracy

Five watts of difference on eleven kilowatts at matched parameter count. It improves physical consistency by a factor of ten instead, which is a different and still useful claim.


## The compute estimate was 64% too optimistic

Dividing a multiply count by a measured multiply rate gave 22.28 milliseconds for the Transformer. Timing the real graph on the chip gave 36.46. The LSTM is worse: 19.84 estimated against 35.07 measured. Both still fit inside the 40 milliseconds allowed, and the estimates remain useful for ranking models against each other, but they cannot be quoted as latencies now that measurements exist.


## Charge conservation cannot be tested at this horizon

The recorded charge channel does not move within a typical three-second window, so the equation has nothing to constrain. Enforcing it costs 4.4% accuracy and buys almost nothing. This was measured rather than argued.


# 35. What changed from the original plan

Twenty-two changes, in two classes, and the distinction matters. Eleven were agreed in the design document before any code was written. Eleven more happened during the eight weeks, each one forced by something that had been measured.


## Agreed before implementation

It is Processor-in-the-Loop, not Hardware-in-the-Loop. The original used HIL throughout. HIL means real electrical hardware in the loop, with motors, power electronics and sensors. There is none of that here, only a processor. Reviewers in embedded and control venues spot a misused HIL immediately, and the correct term costs nothing.

The embedded work moved from last to first, which is the largest single change. The original schedules the ESP32 for weeks 10 and 11, after all the modelling is finished. That is the one arrangement in which a failure has no recovery: if the model does not fit in week 10, there is no time left to build a smaller one. The compute-feasibility question is now gate G1 in week 1, and the plan already names the fallback. This inversion is why the project knew in week 4, rather than week 10, that XGBoost was never deployable.

Real logged trips replaced a physics-generated dataset. The original creates the training data by pushing drive cycles through the physics model, which makes the thing being predicted a closed-form function of the very inputs used to predict it. The model then appears to do brilliantly while having learned nothing about a real car. The predecessor work has exactly this defect. This project trains on 72 real logged trips at 10 Hz instead.

Data is split by trip and never by row. The predecessor split 2,000 rows at random, and because consecutive rows come from the same drive a fraction of a second apart, near-identical samples landed on both sides. The model was effectively tested on data it had trained on, which inflates every score. Here no sample from a trip ever appears on both sides, and the calibration data used for 8-bit quantisation is drawn from training trips only, which is a subtler version of the same leak.

The communication task runs at 10 ms rather than 50. This was arithmetic rather than judgement: the original specifies a 10 ms control loop and a 50 ms communication task, and a loop cannot close five times faster than the messages it depends on arrive.

Budget first, then model. The model size is not chosen and then checked, it is derived from what gate G1 measured. The Transformer is 32 sequence steps, 32 units wide and 2 layers deep because that is what fits in 40 milliseconds on this chip.

The model comparison was rebuilt. Linear regression, random forest and XGBoost became a mandatory naive baseline, one strong tabular model, an LSTM fed genuinely sequential data, and a Transformer, each in plain and physics-informed versions at matched size. Re-running the LSTM correctly is deliberate: the predecessor flattened its data first, which removes the time ordering the architecture exists to exploit, and then reported that recurrent models underperform.

Gates, ablations and explicit non-claims are entirely new. Five gates each with a written action on failure; four numbered ablations; a metrics table with actual metrics where the original listed headings and left them empty; and a list of things this work will explicitly not claim. Stating the non-claims in advance is what allows two null results to be reported as findings rather than as embarrassments.

Thirteen scenario variations became six axes, keeping full robustness coverage at roughly half the runs.

The ESP32-S3 is the primary platform rather than the C6. Two processor cores matter enormously here, because the hard real-time loop is pinned to core 0 where inference on core 1 cannot disturb it. The single-core C6 cannot make that separation at all.

A second, independent dataset was added, held purely as an out-of-distribution check. Building and testing on one car answers whether the model fits; the question a reviewer actually asks is whether it transfers, and nothing in the original plan could have answered it.


## Changed in flight, because something was measured

These are the ones to be most transparent about, because each represents the plan meeting reality. In every case the measurement came first and the change followed.

Gate G2 was split into three parts instead of one pooled number, and this was the one revision the design document permits. Neither threshold was loosened; what changed is which part of the model each threshold is applied to. Applied literally the original criterion failed all seven trips at a median error of 23.7 percent, because that single number pooled three independent models and could not say which was wrong. Driving the plant with the archive's own logged torque drops the error to a median of 7.0 percent, inside the original bound on every trip. The revision is now spent and nothing else may be adjusted without the same treatment.

The control loop became pipelined rather than synchronous. Originally the chip sent a request and then waited for the reply inside the same 10 millisecond slot, tying its deadline to the scheduling behaviour of a general-purpose laptop. It now requests the next state and acts on the most recent one it holds, so it no longer waits for the laptop inside its own time slot. This is a genuine trade rather than a free win, because the controller now acts on information one cycle old, and that cost is measured and reported.

The link runs over the chip's built-in USB rather than a separate adapter. The design deliberately left this open for gate G3 to settle on measured evidence, and the built-in peripheral carries the loop with zero corrupted and zero lost messages.

Three identified parameters were relabelled as lumped losses. The fitted rolling-resistance coefficient came out 2.2 times larger than an independent measurement on a comparable car, so it is not a tyre property. It is a coefficient occupying that place in the equation and absorbing every speed-dependent loss the model does not represent separately. The parameter file says so, and an automated test fails if that statement is removed.

One of the three physics constraints was switched off. Charge conservation has nothing to constrain over a three-second window, because the logged charge channel does not measurably move within one. Its weight is held at zero and the cost of switching it on is reported as its own arm rather than quietly omitted.

The message format grew to carry a real controller. The state message went from 8 numbers to 10 so that the laptop can send the target speed and its rate of change, the command message from 3 to 4, and the diagnostics message from 11 counters to 16. Gate G3 was then re-measured in full, because the loop the report describes has to be the loop that was measured.

The offline optimiser searches two dimensions rather than three. This is not a simplification for speed. With the speed trajectory fixed by the tracking constraint, the battery power limit can only ever remove power the speed controller needs, which the constraint forbids. It is a safety limiter and not an optimisation lever, and that applies to the learned controller in exactly the same way.

Controllers are now ranked with shed cabin heat charged back. Raw consumption is not comparable between controllers, because one that turns the heating down looks excellent without having managed any energy. Without this correction the week 8 table reads as the learned controller saving 1.3 percent; with it, the same controller is 0.66 percent worse, and the entire difference was 48 to 50 watt-hours of cabin heat per cycle.

The learned controller is 64 units wide rather than the library default of 256. The default would be 68,867 numbers and 269 kilobytes, which is 90 percent of the entire memory budget the forecaster also has to fit inside. At 64 wide it is 4,931 numbers and 19.3 kilobytes, and both figures were measured in a pilot run before the main campaign.

XGBoost and the LSTM ensemble were dropped as deployable options. XGBoost needs roughly 3.7 megabytes against a 300 kilobyte budget, over twelve times too large. The best-looking accuracy figure in the whole comparison was a five-model LSTM ensemble, which takes 99 milliseconds against a 40 millisecond budget. Both remain offline reference points, and the reported number is now always distinguished from the deployable one.

The watchdog was switched on and a fallback path built. Three different failures now get three different responses and three separate counters rather than one generic fault state, because collapsing them is how a controller ends up limping owing to a slow logging task. All three were then triggered deliberately on the board, plus a fourth test that hung the control task on purpose to confirm the watchdog resets the chip. A fallback path that has never been taken is a claim, not a result.


# 36. What is left to do

Corrected-model campaign: complete. Corrected-model link-outage sweep: complete. The proposed speed-loop decision transformer was dropped. The classical filter and detector are in the firmware, switched off by default, and were measured on the board in section 29. Open from that section: the detector's threshold has to be redesigned before it can be relied on, and every fault and mismatch scenario remains simulated.

Week 13 closed that open item: the detector was replaced by a new fault checker, measured on the board with injected faults in section 30. Still open after week 13: a real acceleration sensor in place of the simulated drift; repeats of the board runs, done in week 14; a backup speed that does not drift while an alarm is raised; traffic in the speed-planning task of section 32; and a decision on Jev, which section 31 does not recommend for the sensor-fault task.

Week 14 repeated the board runs and tried a backup speed that does not drift and a traffic limit on the planner, all in section 33. Open after week 14: the backup speed's failure on a car heavier than its model, then a version for the chip and a board run; and still a real acceleration sensor.

The following week-by-week plan records the earlier project schedule. Current correction status is stated above.

| Week | Modelling work | Hardware work | Gate |
|---|---|---|---|
| 6 | DONE: 8-bit costs 0.95% accuracy. DONE: the distilled student, which came back empty because the teacher is no better than its students. Section 14 | DONE: 36.46 ms measured on the chip. Still to do: the conversion toolchain, and energy per prediction | G5 |
| 7 | DONE: the offline optimum, the conventional controller, the speed controller and its robustness tests, and the reinforcement-learning ramp-up. The optimum came back smaller than expected; see section 16 | DONE: watchdog and fallback path built, and all four failure modes triggered on the board. Gate G3 re-measured on the changed firmware | - |
| 8 | DONE: five training runs per arm. The learned controller finishes slightly worse than the conventional one, and the forecast makes no measurable difference. Sections 16 and 17 | DONE: the controller runs on the chip, matches Python, and takes 0.121 ms of the 40 allowed | - |
| 9 | Not done, by decision. The missing headroom in section 16 is reported as a negative result, so tuning the reward of a controller chasing a constant has no destination | DONE: ablation A4 measured on the board, predicted in section 19, measured in section 20, and the crossover narrowed to between four and five seconds in section 25 | - |
| 10 | - | DONE: the learned controller runs on the chip (section 23), and every on-chip result was taken again on the Arduino build (section 24). NEXT: the measurement campaign, six scenarios, several controllers, several random starts | - |
| 11 | Analysis and figures | Oscilloscope timing measurements | - |
| 12 | Write up and submit | - | - |


## The two experiments that carried real risk

Both have now been run, and neither turned out the way a hopeful plan would have wanted.

A3 asked whether the forecast actually improves control. Removing it made no measurable difference, so the forecaster does not ship. That is reported as a finding about preview horizons in embedded energy management, not hidden.

The reinforcement learner trained and converged over five runs, and finished slightly worse than the conventional controller. The conventional controller and the offline optimum were there as working comparisons for exactly this case.


## Decisions taken

The missing headroom in the energy-management problem, section 16, is reported as a negative result rather than worked around by widening the problem.

The learned controller trained without the forecast is what runs on the chip, with no forecaster, section 23.

The firmware is built with the Arduino toolchain, and every on-chip result was measured again against it, section 24.


## Decisions still waiting on a gate or on the supervisor

Whether gate G3's zero-lost-frame rule should distinguish a controller that missed its own deadline, of which there are none, from a laptop that answered late, of which there are a few. The counter that separates them was added and measured this week.

Whether to restate gate G4 against the linear regression rather than the naive baseline. Recorded in the design document for G4 to decide.

Whether the road-load variation should become randomised training conditions for the reinforcement learner. The cross-vehicle test says the spread that matters is between vehicles and depends on temperature, which is wider than originally planned for.


## Open, and not waiting on anything

The corrected campaign and outage sweep are complete; the next step is review of the measured correction and paper framing.

The current drawn from the supply on the Arduino build. Only timing was re-measured after the port, and the radios cannot be left out of that build. Deferred on 11 September 2026, so the radio constraint is still supported by argument for current, not by measurement.

The historical four-to-five-second outage crossover is not a conclusion about the corrected plant. Interpret the new sweep from its own paired measurements.

The stand-in workload in the forecaster's slot, which still runs although no forecaster ships. It is kept because the deadline-miss experiments were triggered through it.


# 37. Reproducing everything in this report

Every result comes from a command that can be re-run. The report itself is generated from the result files rather than typed, so its numbers cannot drift from the measurements.

| What | Command |
|---|---|
| Fit the vehicle parameters | python3 scripts/identify_params.py |
| Gate G2, vehicle model | python3 scripts/validate_plant.py |
| Cross-vehicle transfer test | python3 scripts/validate_ved.py |
| Pre-training checks and baselines | python3 scripts/run_guards.py |
| The model comparison | python3 scripts/run_ladder.py |
| Transformer and ablation A1 | python3 scripts/run_transformer.py |
| Cost on the chip | python3 scripts/report_deploy_cost.py |
| Gate G3, real-time loop | ./scripts/g3_campaign.sh 10 |
| Fetch the standard driving cycles | python3 scripts/build_cycles.py |
| Controller baselines and the offline optimum | python3 scripts/run_control_baselines.py |
| Speed-controller robustness | python3 scripts/run_pid_robustness.py |
| Reinforcement-learning ramp-up | python3 scripts/run_rl_rampup.py |
| Train the controller, five seeds, plus ablation A3 | python3 scripts/run_sac.py |
| Export the trained controller to the firmware | python3 scripts/verify_actor.py --export |
| Verify it on the chip (needs -DRUN_ACTOR_BENCH=1) | python3 scripts/verify_actor.py --check |
| Build and flash the firmware | ./scripts/arduino_build.sh --flash |
| Fault-injection build | ./scripts/arduino_build.sh --flash -DFAULT_INJECT=1 |
| Gate G1 on the chip | ./scripts/arduino_build.sh --flash -DRUN_G1_BENCHMARK=1 |
| Gate G5 encoder latency on the chip | ./scripts/arduino_build.sh --flash -DRUN_G5_BENCHMARK=1 |
| Collect a benchmark's output | python3 scripts/capture_bench.py --tag G1 |
| The same firmware under ESP-IDF, the reference build | ./scripts/idf.sh build |
| Fallback path on hardware | python3 scripts/run_fallback.py |
| Watchdog on hardware (needs -DFAULT_INJECT=2) | python3 scripts/run_fallback.py --watchdog |
| 8-bit arithmetic, ablation A2 rungs one and two | python3 scripts/run_a2.py |
| Distilled students, ablation A2 rung three | python3 scripts/run_distill.py |
| Ablation A4 build (handling off) | ./scripts/arduino_build.sh --flash -DFAULT_INJECT=1 -DFALLBACK_ENABLED=0 |
| Ablation A4 with the loop closed | python3 scripts/run_a4_closedloop.py --fallback-off |
| Ablation A4 on hardware | python3 scripts/run_fallback.py --fallback-off |
| Ablation A4 predicted on the laptop | python3 scripts/predict_a4.py |
| This report | python3 scripts/build_report.py |

All Python commands need PYTHONPATH="src:." set. The reinforcement-learning ramp-up additionally needs stable-baselines3 and gymnasium. The test suite runs with python3 -m pytest and currently holds 606 tests, including ones that drive the controller and the learned policy in C and in Python through identical inputs and require them to agree, and ones that read the firmware's own compile-time switches back out of its headers so that the scripts describing them cannot drift from what is compiled.
