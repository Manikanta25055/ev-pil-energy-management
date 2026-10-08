CFLAGS = -std=c11 -Wall -Wextra -Werror -O1 -I../main

test_protocol: test_protocol.c ../main/protocol.c
	$(CC) $(CFLAGS) -o $@ $^

# Dumps the on-device controller's output for a fixed input sequence.
# tests/control/test_c_parity.py builds this and diffs it against the Python
# controller, which is how the two are kept from drifting apart.
test_control: test_control.c ../main/control.c
	$(CC) $(CFLAGS) -o $@ $^ -lm

# Dumps the block features the decision model reads.
# tests/control/test_features_c_parity.py diffs it against the Python copy.
test_features: test_features.c ../main/features.c
	$(CC) $(CFLAGS) -o $@ $^ -lm

# Built against a weights header supplied on the include path, so the same
# inference code the board runs can be checked without a board. The header
# comes from evpil.control.actor.write_c_header; ACTOR_INC points at whichever
# directory holds it.
# ACTOR_INC comes BEFORE CFLAGS, which already carries -I../main. With the
# order reversed the compiler found firmware/main/sac_actor_weights.h first
# and the harness silently tested the deployed policy instead of the one the
# caller asked for. It passed while no deployed header existed and started
# failing the moment one did, which is the worst possible time to find out.
ACTOR_INC ?= ../main
test_actor: test_actor.c ../main/actor.c
	$(CC) -I$(ACTOR_INC) $(CFLAGS) -o $@ $^ -lm

# The action decode, checked against EnergyManagementEnv.decode_action by
# tests/control/test_decode_c_parity.py. Needs the same weights header as
# test_actor, because the decode bounds are exported with the weights.
test_decode: test_decode.c ../main/actor.c
	$(CC) -I$(ACTOR_INC) $(CFLAGS) -o $@ $^ -lm

# The learned reviewer's cell, against a weights header on the include path
# written by evpil.control.tiny_rnn.write_c_header. REVIEWER_INC first, for
# the reason ACTOR_INC is.
REVIEWER_INC ?= ../main
test_reviewer: test_reviewer.c ../main/reviewer.c
	$(CC) -I$(REVIEWER_INC) $(CFLAGS) -o $@ $^ -lm

.PHONY: check clean
check: test_protocol test_control test_features
	./test_protocol
	./test_control > /dev/null && echo "ok:   control dump builds and runs"
	./test_features > /dev/null && echo "ok:   feature dump builds and runs"

clean:
	rm -f test_protocol test_control test_actor test_decode test_features
