VERSION = 2.0.0
CC = gcc
CFLAGS = -m64 -O3 -Wall -lpthread -fPIE -fstack-protector -Wno-incompatible-pointer-types
CFLAGS_RELEASE = -m64 -O3 -Wall -lpthread -fPIE -s -DNDEBUG -Wno-incompatible-pointer-types

.PHONY: all release clean install uninstall

all: thread_socket

thread_socket:
	$(CC) $(CFLAGS) -o $(@) thread_socket.c driver.c

release:
	$(CC) $(CFLAGS_RELEASE) -o thread_socket thread_socket.c driver.c
	strip thread_socket
	@echo "Built release version $(VERSION)"

clean:
	rm -f ./thread_socket

install:
	cp -f ./thread_socket /usr/bin

uninstall:
	rm -f /usr/bin/thread_socket
