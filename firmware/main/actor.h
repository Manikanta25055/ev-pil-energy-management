#pragma once
#include <stdint.h>

/* On-device inference for the exported SAC actor.

   The weights live in a generated header (`sac_actor_weights.h`, written by
   evpil.control.actor.write_c_header) so that the policy the firmware runs is
   the policy that was trained. Hand-editing that header would produce a
   controller nobody trained and no test would notice.

   Only the actor ships. The critic is training scaffolding, and the Gaussian
   the actor parameterises is a training-time behaviour: at evaluation the
   standard deviation is unused and the action is tanh of the mean, so there
   is no reason to put a random number generator on a microcontroller. */

/* Scale and clip a raw observation the way evpil.control.env does. Kept here
   rather than on the host so that a device running against a live plant does
   not depend on the host to prepare its inputs. */
void actor_scale_observation(const float *raw, float *scaled, int n);

/* Deterministic action in [-1, 1]. `scaled` has ACTOR_N_IN entries, `action`
   has ACTOR_N_OUT. Returns the elapsed time in microseconds. */
uint32_t actor_forward(const float *scaled, float *action);

/* Digest of the weights this translation unit was compiled against. Shape
   does not identify a network: two policies trained from different seeds have
   identical geometry and different behaviour. */
uint32_t actor_checksum(void);

/* Map a policy output in [-1, 1]^3 to a physical energy-management action.
   Mirrors EnergyManagementEnv.decode_action, against bounds the exporter
   writes into the generated header rather than bounds defined here: a policy
   decoded against different limits is a different controller, and it fails
   silently because every number it produces is still in range.

   Declared in terms of the three floats rather than ems_action_t so that this
   header does not have to pull in control.h. */
void actor_decode_action_raw(const float *action, float *regen_blend,
                             float *p_limit_w, float *aux_derate);

/* Layer geometry of the compiled-in actor, for the diagnostics frame. */
int actor_n_in(void);
int actor_n_out(void);
int actor_n_params(void);
