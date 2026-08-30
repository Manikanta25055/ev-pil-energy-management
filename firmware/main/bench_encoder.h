#pragma once
#include <stdint.h>

/* Times one forward pass of the deployed encoder shape on this silicon.

   G1 measured a raw int8 multiply-accumulate rate and G5's budget was then
   estimated by dividing a MAC count by it. That estimate ignores everything
   that is not a multiply: softmax, layer normalisation, requantisation, and
   the memory traffic of moving 32x32 tiles around. This runs the real shapes
   so the latency figure is measured rather than divided.

   The weights are filled with a fixed pattern rather than the trained ones.
   That makes this a latency measurement and nothing else: the numbers it
   produces say how long the graph takes, not what it would predict. */
void bench_encoder_report(void);
