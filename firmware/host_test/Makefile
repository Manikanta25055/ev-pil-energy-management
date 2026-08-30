CFLAGS = -std=c11 -Wall -Wextra -Werror -O1 -I../main

test_protocol: test_protocol.c ../main/protocol.c
	$(CC) $(CFLAGS) -o $@ $^

.PHONY: check clean
check: test_protocol
	./test_protocol

clean:
	rm -f test_protocol
