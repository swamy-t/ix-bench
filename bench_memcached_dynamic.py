#!/usr/bin/env python

import os
import argparse
import shlex
import time
import spur
import getpass

import bench_common

CONNECTIONS = 2720
DEPTH = 4
IX_PORT = 8000
LATENCY_CONNECTIONS = 32
LATENCY_QPS = 2000
RECORDS = 1000000
THREADS = 16
TIME = 300
WARMUP = 60

WORKLOADS = {
  'etc': '--keysize=fb_key --valuesize=fb_value --iadist=fb_ia --update=0.033',
  'usr': '--keysize=19 --valuesize=2 --update=0.002',
}

PATTERNS = {
  'triangle': '--qps-function=triangle:10000:6300000:240:0',
  'qtriangle': '--qps-function=qtriangle:700000:6300000:240:500000',
  'sin_noise': '--qps-function=sin_noise:500000:6000000:240:250000:5',
}

DIR = '/tmp/' + getpass.getuser()

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--ix', required=True)
  parser.add_argument('--workload', choices=WORKLOADS.keys(), required=True)
  parser.add_argument('--pattern', choices=PATTERNS.keys(), required=True)
  parser.add_argument('--with-background-job', action='store_true', dest='background')
  parser.add_argument('--mutilate', required=True)
  parser.add_argument('--memcached', required=True)
  parser.add_argument('--outdir', required=True)
  parser.add_argument('server')
  parser.add_argument('client', nargs='+')
  args = parser.parse_args()

  if not os.path.exists(args.outdir):
    os.makedirs(args.outdir)

  server = spur.SshShell(args.server, missing_host_key = spur.ssh.MissingHostKey.accept)
  clients = []
  for client_name in args.client:
    clients.append(spur.SshShell(client_name, missing_host_key = spur.ssh.MissingHostKey.accept))

  server_deploy = [args.ix + '/dp/ix', args.ix + '/cp/ixcp.py', args.memcached]
  if args.background:
    server_deploy.append('sha1_bench')
  bench_common.deploy(server, server_deploy)
  for client in clients:
    bench_common.deploy(client, [args.mutilate])

  with bench_common.ProcessManager() as proc_manager:
    channel, pid = proc_manager.spawn(server, 'sudo stdbuf -o0 -e0  %(DIR)s/ix -c /etc/ix.conf --  %(DIR)s/memcached -k -Mm 1024 -c 4096 -o hashpower=20' % {'DIR' : DIR}, 'sudo kill {pid}')
    bench_common.wait_for_network(clients[0], bench_common.get_host_ip(server), IX_PORT)
    bench_common.consume(channel)

    if args.background:
      server.run(shlex.split('rm -f  %(DIR)s/sha1_bench.control' % {'DIR' : DIR}))
      server.run(shlex.split('mkfifo  %(DIR)s/sha1_bench.control' % {'DIR' : DIR}))
      proc, background_pid = proc_manager.spawn(server, 'stdbuf -o0 -e0 %(DIR)s/sha1_bench -T 0 -s 41943040 -c  %(DIR)s/sha1_bench.control' % {'DIR' : DIR}, 'kill {pid}')
      proc.settimeout(1)
      sha1_bench = proc.makefile('rb')
      server.run(shlex.split('sudo chrt -rap 99 %d' % background_pid))

    server.run(shlex.split('sudo sh -c "rm -f  %(DIR)s/block-*.fifo"' % {'DIR' : DIR}))
    server.run(shlex.split('sudo  %(DIR)s/ixcp.py --cpus 1' % {'DIR' : DIR}), cwd = DIR)

    if args.background:
      cores = bench_common.get_cores(server)
      cores = cores[:len(cores)/2]
      cores.reverse()
      cores = ','.join(cores)
      proc, _ = proc_manager.spawn(server, 'sudo stdbuf -o0 -e0  %(DIR)s/ixcp.py --control back --background-cpus %(cores)s --background-fifo %(DIR)s/sha1_bench.control --background-pid %(background_pid)d' % {'DIR' : DIR, 'cores': cores, 'background_pid': background_pid}, 'sudo kill {pid}', cwd = DIR)
      proc.settimeout(1)
      ixcp = proc.makefile('rb')
      server.run(shlex.split('kill -USR1 %d' % (background_pid,)))
    else:
      proc, _ = proc_manager.spawn(server, 'sudo stdbuf -o0 -e0  %(DIR)s/ixcp.py --control eff' % {'DIR' : DIR}, 'sudo kill {pid}', cwd = DIR)
      proc.settimeout(1)
      ixcp = proc.makefile('rb')

    cmdline = ' --server=%s:%d %s --report-stats=1 %s --qps-warmup=%d' % (bench_common.get_host_ip(server), IX_PORT, WORKLOADS[args.workload], PATTERNS[args.pattern], WARMUP)
    mutilate = bench_common.mutilate_benchmark(proc_manager, clients, cmdline, CONNECTIONS, THREADS, RECORDS, DEPTH, LATENCY_CONNECTIONS, LATENCY_QPS, TIME)
    ixcp = bench_common.generator_from_file(ixcp)

    mutilate_file = open(args.outdir + '/mutilate.out', 'w')
    ixcp_file = open(args.outdir + '/ixcp.out', 'w')
    for src, line in bench_common.multiplexer(mutilate, ixcp):
      if src == 0:
        if line is None:
          break
        print >>mutilate_file, line[:-1],
        print >>mutilate_file, server.run(shlex.split('sudo  %(DIR)s/ixcp.py --print-power' % {'DIR' : DIR})).output[:-1],
        if args.background:
          server.run(shlex.split('kill -USR1 %d' % (background_pid,)))
          line = bench_common.readline_retry(sha1_bench)[:-1]
          parts = line.split()
          print >>mutilate_file, parts[3]
        else:
          print >>mutilate_file, ''
      elif src == 1:
        print >>ixcp_file, line[:-1]

if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    pass
