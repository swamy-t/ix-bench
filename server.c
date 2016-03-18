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

#include <errno.h>
#include <event2/bufferevent.h>
#include <event2/listener.h>
#include <netinet/tcp.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define CORES 32

struct worker {
	int cpu;
	struct event_base *base;
	pthread_t tid;
	int enable;
} worker[CORES];

struct ctx {
	struct worker *worker;
	size_t bytes_left;
	unsigned char *buffer;
};

static int msg_size;

static struct ctx *init_ctx(struct worker *worker)
{
	struct ctx *ctx;
	ctx = malloc(sizeof(struct ctx));
	ctx->worker = worker;
	ctx->bytes_left = msg_size;
	ctx->buffer = malloc(msg_size);
	return ctx;
}

static void echo_event_cb(struct bufferevent *bev, short events, void *arg)
{
	if (events & BEV_EVENT_EOF) {
		fprintf(stderr, "Connection terminated prematurely.\n");
		exit(1);
	}

	if (events & BEV_EVENT_ERROR) {
		bufferevent_free(bev);
		return;
	}

	if (events & BEV_EVENT_WRITING) {
		bufferevent_free(bev);
		return;
	}

	if (events & BEV_EVENT_READING) {
		bufferevent_free(bev);
		return;
	}

	if (events & BEV_EVENT_TIMEOUT) {
		bufferevent_free(bev);
		return;
	}

	fprintf(stderr, "uncaught event %d\n", events);
	exit(1);
}

static void echo_read_cb(struct bufferevent *bev, void *arg)
{
	struct ctx *ctx = arg;
	size_t len;

	len = bufferevent_read(bev, &ctx->buffer[msg_size - ctx->bytes_left], ctx->bytes_left);
	ctx->bytes_left -= len;
	if (!ctx->bytes_left) {
		ctx->bytes_left = msg_size;
		bufferevent_write(bev, ctx->buffer, msg_size);
	}
}

static void accept_conn_cb(struct evconnlistener *listener, evutil_socket_t fd, struct sockaddr *address, int socklen, void *arg)
{
	struct bufferevent *bev;
	struct ctx *ctx;
	struct worker *worker = arg;
	int flag;

	flag = 1;
	if (setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, (void *) &flag, sizeof(flag))) {
		perror("setsockopt(TCP_NODELAY)");
		exit(1);
	}

	bev = bufferevent_socket_new(worker->base, fd, BEV_OPT_CLOSE_ON_FREE);
	ctx = init_ctx(worker);
	bufferevent_setcb(bev, echo_read_cb, NULL, echo_event_cb, ctx);
	bufferevent_enable(bev, EV_READ | EV_WRITE);
}

static void accept_error_cb(struct evconnlistener *listener, void *arg)
{
	struct event_base *base = evconnlistener_get_base(listener);
	int err = EVUTIL_SOCKET_ERROR();
	fprintf(stderr, "Got an error %d (%s) on the listener. Shutting down.\n", err, evutil_socket_error_to_string(err));

	event_base_loopexit(base, NULL);
}

static void *start_worker(void *p)
{
	struct worker *worker;
	struct evconnlistener *listener;
	struct sockaddr_in sin;
	int sock;
	int one;

	worker = p;

	worker->base = event_base_new();
	if (!worker->base) {
		puts("Couldn't open event base");
		exit(1);
	}

	sock = socket(AF_INET, SOCK_STREAM, 0);
	if (!sock) {
		perror("socket");
		exit(1);
	}

	evutil_make_socket_nonblocking(sock);

	one = 1;
	if (setsockopt(sock, SOL_SOCKET, SO_REUSEPORT, (void *) &one, sizeof(one))) {
		perror("setsockopt(SO_REUSEPORT)");
		exit(1);
	}

	memset(&sin, 0, sizeof(sin));
	sin.sin_family = AF_INET;
	sin.sin_addr.s_addr = htonl(0);
	sin.sin_port = htons(9876);

	if (bind(sock, (struct sockaddr*)&sin, sizeof(sin))) {
		perror("bind");
		exit(1);
	}

	listener = evconnlistener_new(worker->base, accept_conn_cb, worker, LEV_OPT_CLOSE_ON_FREE | LEV_OPT_REUSEABLE, -1, sock);
	if (!listener) {
		perror("Couldn't create listener");
		exit(1);
	}
	evconnlistener_set_error_cb(listener, accept_error_cb);

	event_base_dispatch(worker->base);

	exit(1);
}

static int start_threads(void)
{
	int i;

	for (i = 0; i < CORES; i++) {
		if (!worker[i].enable)
			continue;
		worker[i].cpu = i;
		pthread_create(&worker[i].tid, NULL, start_worker, &worker[i]);
	}

	return 0;
}

static int parse_cpus(char *cpus)
{
	int cpu_count;
	int i;
	int val;
	char *tok;

	cpu_count = sysconf(_SC_NPROCESSORS_CONF);
	if (cpu_count > CORES) {
		fprintf(stderr, "Error: You have %d CPUs. The maximum supported number is %d.'\n", cpu_count, CORES);
		return 1;
	}

	if (cpus) {
		tok = strtok(cpus, ",");
		while (tok) {
			val = atoi(tok);
			if (val < 0 || val >= cpu_count) {
				fprintf(stderr, "Error: Invalid CPU specified '%s'\n", tok);
				return 1;
			}
			worker[val].enable = 1;

			tok = strtok(NULL, ",");
		}
	} else {
		for (i = 0; i < cpu_count; i++)
			worker[i].enable = 1;
	}

	return 0;
}

void usage(char *me)
{
	fprintf(stderr, "Usage: %s MSG_SIZE [CPUS]\n", me);
	exit(1);
}

int main(int argc, char **argv)
{
	int ret;

	if (argc < 2)
		usage(argv[0]);

	msg_size = atoi(argv[1]);

	ret = parse_cpus(argc > 2 ? argv[2] : NULL);
	if (ret)
		usage(argv[0]);

	start_threads();

	while (1)
		pause();

	return 0;
}
