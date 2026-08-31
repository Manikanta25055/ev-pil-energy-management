#pragma once

/* Verify and time the exported SAC actor on silicon.

   Runs a fixed set of observations, prints each action, and reports the
   per-inference latency. The host compares the printed actions against the
   same actor evaluated in numpy (scripts/verify_actor.py), which is the same
   parity discipline protocol.c and control.c already follow. */
/* Measure once, then print the report on a two-second loop. Does not return.
   The repeat is not decoration: the console shares the USB peripheral, which
   delivers nothing to the first host connection after a reset, so a report
   printed once at boot is usually a report nobody sees. */
void bench_actor_report(void);

void bench_actor_measure(void);
void bench_actor_print(void);
