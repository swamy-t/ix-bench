#!/usr/bin/env python

import argparse
import getpass
import shlex
import spur

import bench_common

CONNECTIONS = 2720
DEPTH = 4
IX_PORT = 8000
LATENCY_CONNECTIONS = 32
LATENCY_QPS = 2000
LINUX_PORT = 11211
RECORDS = 1000000
SCAN = 'triangle:10000:6500000:240:0'
THREADS = 16
TIME = 120

WORKLOADS = {
  'etc': '--keysize=fb_key --valuesize=fb_value --iadist=fb_ia --update=0.033',
  'usr': '--keysize=19 --valuesize=2 --update=0.002',
}

DIR = '/tmp/' + getpass.getuser()

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--target', choices=['linux', 'ix'], required=True)
  parser.add_argument('--workload', choices=WORKLOADS.keys(), required=True)
  parser.add_argument('--mutilate', required=True)
  parser.add_argument('--memcached', required=True)
  parser.add_argument('--batch')
  parser.add_argument('--ix')
  parser.add_argument('server')
  parser.add_argument('client', nargs='+')
  args = parser.parse_args()

  server = spur.SshShell(args.server, missing_host_key = spur.ssh.MissingHostKey.accept)
  clients = []
  for client_name in args.client:
    clients.append(spur.SshShell(client_name, missing_host_key = spur.ssh.MissingHostKey.accept))

  server_deploy = [args.memcached]
  if args.target == 'ix':
    server_deploy.extend([args.ix + '/dp/ix', args.ix + '/cp/ixcp.py'])
  bench_common.deploy(server, server_deploy)
  for client in clients:
    bench_common.deploy(client, [args.mutilate])

  server.run(shlex.split('cp /etc/ix.conf '+DIR+'/ix.conf'))
  if args.batch is not None:
    server.run(shlex.split("sed -i 's/^batch=.*/batch={0}/' ".format(args.batch)+DIR+"/ix.conf"))

  with bench_common.ProcessManager() as proc_manager:
    if args.target == 'linux':
      port = LINUX_PORT
      cores = bench_common.get_cores(server)
      core_count = len(cores)
      cores = ','.join(cores)
      numa_node = int(server.run(shlex.split('cat /sys/devices/system/cpu/cpu%s/topology/physical_package_id' % cores[0])).output)
      proc_manager.spawn(server, 'stdbuf -o0 -e0 numactl -m %(numa_node)d %(DIR)s/memcached -k -Mm 1024 -c 4096 -o hashpower=20 -b 8192 -t %(core_count)d -T %(cores)s' % {'DIR': DIR, 'numa_node': numa_node, 'core_count': core_count, 'cores': cores}, 'kill {pid}')
      bench_common.wait_for_network(clients[0], bench_common.get_host_ip(server), port)
    elif args.target == 'ix':
      port = IX_PORT
      channel, pid = proc_manager.spawn(server, 'sudo stdbuf -o0 -e0 %(DIR)s/ix -c %(DIR)s/ix.conf -- %(DIR)s/memcached -k -Mm 1024 -c 4096 -o hashpower=20' % {'DIR': DIR}, 'sudo kill {pid}')
      bench_common.wait_for_network(clients[0], bench_common.get_host_ip(server), port)
      bench_common.consume(channel)

    cmdline = '--server=%s:%d %s --qps-function=%s --report-stats=1 --stop-latency=50:750' % (bench_common.get_host_ip(server), port, WORKLOADS[args.workload], SCAN)
    mutilate = bench_common.mutilate_benchmark(proc_manager, clients, cmdline, CONNECTIONS, THREADS, RECORDS, DEPTH, LATENCY_CONNECTIONS, LATENCY_QPS, TIME)

    for line in mutilate:
      if line is None:
        break
      if line[0] not in '01234567890 #':
        continue
      print line[:-1]

if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    pass
