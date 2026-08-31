CFLAGS = -std=c11 -Wall -Wextra -Werror -O1 -I../main

test_protocol: test_protocol.c ../main/protocol.c
	$(CC) $(CFLAGS) -o $@ $^

# Dumps the on-device controller's output for a fixed input sequence.
# tests/control/test_c_parity.py builds this and diffs it against the Python
# controller, which is how the two are kept from drifting apart.
test_control: test_control.c ../main/control.c
	$(CC) $(CFLAGS) -o $@ $^ -lm

.PHONY: check clean
check: test_protocol test_control
	./test_protocol
	./test_control > /dev/null && echo "ok:   control dump builds and runs"

clean:
	rm -f test_protocol test_control
