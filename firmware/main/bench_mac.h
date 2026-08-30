#pragma once
#include <stdint.h>

/* Runs an int8 x int8 -> int32 accumulation of `n` MACs, `reps` times.
   Returns elapsed microseconds for all reps combined. */
uint32_t bench_mac_run(int n, int reps);

/* Prints one EVPIL-G1 line per size in the sweep. */
void bench_mac_report(void);
