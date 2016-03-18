/*
 * Copyright 2013-16 Board of Trustees of Stanford University
 * Copyright 2013-16 Ecole Polytechnique Federale Lausanne (EPFL)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#define _GNU_SOURCE

#include <arpa/inet.h>
#include <errno.h>
#include <event2/buffer.h>
#include <event2/bufferevent.h>
#include <event2/listener.h>
#include <netinet/tcp.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#define MAX_CORES 128

struct worker {
	struct event_base *base;
	pthread_t tid;
	char *buffer;
	int connections;
	long total_messages;
} worker[MAX_CORES];

struct ctx {
	struct worker *worker;
	int bytes_left;
	long messages_left;
	struct bufferevent *bev;
};

static struct sockaddr_in server_addr;
static long messages_per_connection;
static int msg_size;
static int ready;

static void new_connection(struct ctx *ctx);

static void send_next_msg(struct ctx *ctx)
{
	ctx->bytes_left = msg_size;

	if (!ctx->messages_left) {
		bufferevent_free(ctx->bev);
		new_connection(ctx);
		return;
	}

	ctx->messages_left--;

	bufferevent_write(ctx->bev, ctx->worker->buffer, ctx->bytes_left);
}

static void echo_read_cb(struct bufferevent *bev, void *arg)
{
	struct ctx *ctx = arg;

	int len;
	struct evbuffer *input = bufferevent_get_input(bev);

	if (!ready) {
		if (__sync_bool_compare_and_swap(&ready, 0, 1)) {
			puts("ready");
			fflush(stdout);
		}
	}

	len = evbuffer_get_length(input);
	evbuffer_drain(input, len);
	ctx->bytes_left -= len;
	if (!ctx->bytes_left) {
		ctx->worker->total_messages++;
		send_next_msg(ctx);
	}
}

static void echo_event_cb(struct bufferevent *bev, short events, void *arg)
{
	if (events == BEV_EVENT_CONNECTED)
		return;

	if (events == BEV_EVENT_ERROR)
		return;

	if (events == (BEV_EVENT_ERROR | BEV_EVENT_READING))
		return;

	if (events == (BEV_EVENT_EOF | BEV_EVENT_READING))
		return;

	fprintf(stderr, "uncaught event %d\n", events);
	exit(1);
}

static void new_connection(struct ctx *ctx)
{
	int s;
	struct linger linger;
	int flag;

	s = socket(AF_INET, SOCK_STREAM, 0);
	if (s == -1) {
		perror("socket");
		exit(1);
	}

	linger.l_onoff = 1;
	linger.l_linger = 0;
	if (setsockopt(s, SOL_SOCKET, SO_LINGER, (void *) &linger, sizeof(linger))) {
		perror("setsockopt(SO_LINGER)");
		exit(1);
	}

	flag = 1;
	if (setsockopt(s, IPPROTO_TCP, TCP_NODELAY, (void *) &flag, sizeof(flag))) {
		perror("setsockopt(TCP_NODELAY)");
		exit(1);
	}

	evutil_make_socket_nonblocking(s);

	ctx->bev = bufferevent_socket_new(ctx->worker->base, s, BEV_OPT_CLOSE_ON_FREE);

	if (bufferevent_socket_connect(ctx->bev, (struct sockaddr *) &server_addr, sizeof(server_addr)) == -1) {
		fprintf(stderr, "bufferevent_socket_connect failed (errno=%d)\n", errno);
		exit(1);
	}

	bufferevent_setcb(ctx->bev, echo_read_cb, NULL, echo_event_cb, ctx);
	bufferevent_enable(ctx->bev, EV_READ);

	ctx->messages_left = messages_per_connection;
	send_next_msg(ctx);
}

static void *start_worker(void *p)
{
	int i;
	struct worker *worker;
	struct ctx *ctx;

	worker = p;

	worker->buffer = malloc(msg_size);
	for (i = 0; i < msg_size; i++)
		worker->buffer[i] = '0';

	worker->base = event_base_new();
	if (!worker->base) {
		fprintf(stderr, "Couldn't open event base\n");
		exit(1);
	}

	for (i = 0; i < worker->connections; i++) {
		ctx = malloc(sizeof(struct ctx));
		ctx->worker = worker;
		new_connection(ctx);
	}

	event_base_dispatch(worker->base);

	return 0;
}

static int start_threads(int cores, int connections)
{
	int i;
	int connections_per_core = connections / cores;
	int leftover_connections = connections % cores;

	for (i = 0; i < cores; i++) {
		worker[i].connections = connections_per_core + (i < leftover_connections ? 1 : 0);
		pthread_create(&worker[i].tid, NULL, start_worker, &worker[i]);
	}

	return 0;
}

int main(int argc, char **argv)
{
	int connections;
	int cores;
	long total_messages;
	int i;
	int ret;
	char buf;

	if (argc < 6) {
		fprintf(stderr, "Usage: %s IP PORT CONNECTIONS MSG_SIZE MESSAGES_PER_CONNECTION\n", argv[0]);
		return 1;
	}

	server_addr.sin_family = AF_INET;
	if (!inet_aton(argv[1], &server_addr.sin_addr)) {
		fprintf(stderr, "Invalid server IP address \"%s\".\n", argv[1]);
		return 1;
	}
	server_addr.sin_port = htons(atoi(argv[2]));
	connections = atoi(argv[3]);
	msg_size = atoi(argv[4]);
	messages_per_connection = strtol(argv[5], NULL, 10);

	cores = sysconf(_SC_NPROCESSORS_CONF);

	start_threads(cores, connections);

	while (1) {
		ret = read(STDIN_FILENO, &buf, 1);
		if (ret == 0) {
			fprintf(stderr, "Error: EOF on STDIN.\n");
			return 1;
		} else if (ret == -1) {
			perror("read");
			return 1;
		}

		total_messages = 0;
		for (i = 0; i < cores; i++)
			total_messages += worker[i].total_messages;

		printf("%d %ld\n", msg_size, total_messages);
		fflush(stdout);
	}

	return 0;
}
