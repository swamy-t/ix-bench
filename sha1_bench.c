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
#include <fcntl.h>
#include <openssl/sha.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>

#define HASH_LEN 65536
#define MAX_THREAD_COUNT 64

#define ROUND_UP(num, multiple) ((((num) + (multiple) - 1) / (multiple)) * (multiple));

static unsigned int thread_count;
static unsigned int duration;
static size_t working_set_size;
static char *mem;
static struct thread_data {
	unsigned long processed_bytes;
	char stop;
} thread_data[MAX_THREAD_COUNT];
static unsigned long prv_print_timestamp;
static char *control_fifo;
static pthread_t thread[MAX_THREAD_COUNT];

static inline void perror_exit(const char *s)
{
	perror(s);
	exit(EXIT_FAILURE);
}

static void *bench_thread(void *arg)
{
	SHA_CTX ctx;
	char *p;
	struct thread_data *data;

	data = (struct thread_data *) arg;
	SHA1_Init(&ctx);

	while (1) {
		for (p = mem; p < mem + working_set_size; p += HASH_LEN) {
			SHA1_Update(&ctx, p, HASH_LEN);
			data->processed_bytes += HASH_LEN;
			if (data->stop)
				return 0;
		}
	}

	return 0;
}

static unsigned long gettime_in_ms(void)
{
	struct timeval tv;
	gettimeofday(&tv, NULL);
	return tv.tv_sec * 1000000 + tv.tv_usec;
}

static void print_stats_handler(int signum)
{
	int i;
	unsigned long sum;
	unsigned long now;
	unsigned long print_interval;

	now = gettime_in_ms();
	print_interval = now - prv_print_timestamp;
	prv_print_timestamp = now;

	sum = 0;
	for (i = 0; i < thread_count; i++) {
		sum += thread_data[i].processed_bytes;
		thread_data[i].processed_bytes = 0;
	}
	printf("SHA1 speed = %.2f MB/sec\n", (double) sum / 1024 / 1024 / print_interval * 1000000);
	fflush(stdout);
}

static void start_thread(unsigned int i)
{
	int ret;

	ret = pthread_create(&thread[i], NULL, bench_thread, &thread_data[i]);
	if (ret)
		perror_exit("pthread_create");
}

static void control_loop()
{
	int fd;
	ssize_t bytes;
	char buf[16];
	int threads;
	int count;
	int i;
	int ret;

	while (1) {
		fd = open(control_fifo, O_RDONLY);
		if (fd == -1 && errno == EINTR)
			continue;
		else if (fd == -1)
			perror_exit("open");

		bytes = read(fd, buf, sizeof(buf));
		if (bytes == -1)
			perror_exit("read");
		else if (bytes == 0)
			goto cont;

		/* FIXME: handle incomplete reads */

		count = sscanf(buf, "%d", &threads);
		if (!count)
			goto cont;

		for (i = 0; i < threads; i++)
			if (!thread[i])
				start_thread(i);

		for (i = threads; i < MAX_THREAD_COUNT; i++) {
			if (thread[i]) {
				thread_data[i].stop = 1;
				ret = pthread_join(thread[i], NULL);
				if (ret)
					perror_exit("pthread_join");
				thread[i] = 0;
				thread_data[i].stop = 0;
			}
		}

		thread_count = threads;
cont:
		close(fd);
	}
}

static void bench()
{
	int i;
	struct sigaction action;

	mem = malloc(working_set_size);
	if (!mem)
		perror_exit("malloc");

	prv_print_timestamp = gettime_in_ms();

	for (i = 0; i < thread_count; i++)
		start_thread(i);

	if (duration) {
		sleep(duration);
		print_stats_handler(0);
	} else {
		action.sa_handler = print_stats_handler;
		sigemptyset(&action.sa_mask);
		action.sa_flags = 0;
		sigaction(SIGUSR1, &action, NULL);

		if (control_fifo)
			control_loop();

		while (1)
			pause();
	}
}

int main(int argc, char **argv)
{
	int c;

	while ((c = getopt(argc, argv, "T:t:s:c:")) != -1) {
		switch (c) {
		case 'T':
			thread_count = atoi(optarg);
			break;
		case 't':
			duration = atoi(optarg);
			break;
		case 's':
			working_set_size = atol(optarg);
			break;
		case 'c':
			control_fifo = strdup(optarg);
			break;
		}
	}

	working_set_size = ROUND_UP(working_set_size, HASH_LEN);

	bench();

	return 0;
}
