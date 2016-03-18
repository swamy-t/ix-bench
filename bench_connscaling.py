#!/usr/bin/env python

import argparse
import getpass
import re
import shlex
import socket
import spur

import bench_common

IX_PORT = 8000
LINUX_PORT = 9876
DEF_MSG_SIZE = 64

def bench(server, clients, connections_per_client, port, core_count, ix_channel):
  kstats_re = re.compile(r'.*non idle cycles=(?P<non_idle_cycles>[0-9]*).*LLC load misses=(?P<llc_load_misses>[0-9]*) \((?P<pkts>[0-9]*) pkts, avg batch=(?P<avg_batch>[0-9]*)')

  if ix_channel is None:
    duration = 5
  else:
    duration = 15

  with bench_common.ProcessManager() as proc_manager:
    clients_ = bench_common.Clients(proc_manager, clients, 'stdbuf -o0 -e0 /tmp/'+getpass.getuser()+'/client %s %d %d %d %d' % (bench_common.get_host_ip(server), port, connections_per_client, DEF_MSG_SIZE, 999999999), 'kill {pid}', duration = duration)
    print '%d %d' % (connections_per_client * len(clients), clients_.run()),
    if ix_channel is None:
      print
    else:
      f = ix_channel.makefile('rb')
      count = 0
      while count < core_count:
        line = f.readline()
        if 'BEGIN' in line:
          count += 1
      non_idle_cycles = 0
      llc_load_misses = 0
      pkts = 0
      avg_batch = 0
      count = 0
      llc = []
      while count < core_count:
        line = f.readline()
        if 'BEGIN' in line:
          count += 1
          m = kstats_re.match(line)
          non_idle_cycles += int(m.group('non_idle_cycles'))
          llc_load_misses += int(m.group('llc_load_misses'))
          pkts += int(m.group('pkts'))
          avg_batch += int(m.group('avg_batch'))
      print '%f (%f,%f,%f,%f,%f,%f) %f' % (1.0 * non_idle_cycles / pkts, 1.0 * llc_load_misses / pkts, 1.0 * llc_load_misses2 / pkts, 1.0 * llc_load_misses3 / pkts, 1.0 * llc_load_misses4 / pkts, 1.0 * llc_load_misses5 / pkts, 1.0 * llc_load_misses6 / pkts, 1.0 * avg_batch / core_count)
      while True:
        try:
          f.readline()
        except socket.timeout:
          break

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--target', choices=['linux', 'ix'], required=True)
  parser.add_argument('--ix')
  parser.add_argument('--kstats')
  parser.add_argument('server')
  parser.add_argument('client', nargs='+')
  args = parser.parse_args()

  server = spur.SshShell(args.server, missing_host_key = spur.ssh.MissingHostKey.accept)
  clients = []
  for client_name in args.client:
    clients.append(spur.SshShell(client_name, missing_host_key = spur.ssh.MissingHostKey.accept))

  if args.target == 'linux':
    server_deploy = ['server']
  elif args.target == 'ix':
    server_deploy = [args.ix + '/dp/ix', args.ix + '/apps/echoserver']
  bench_common.deploy(server, server_deploy)
  for client in clients:
    bench_common.deploy(client, ['client'])

  cores = bench_common.get_cores(server)

  with bench_common.ProcessManager() as proc_manager:
    if args.target == 'linux':
      port = LINUX_PORT
      core_str = ','.join([str(x) for x in cores])
      proc_manager.spawn(server, '/tmp/'+getpass.getuser()+'/server %d %s' % (DEF_MSG_SIZE, core_str), 'kill {pid}')
    elif args.target == 'ix':
      port = IX_PORT
      channel, pid = proc_manager.spawn(server, 'sudo stdbuf -o0 -e0 /tmp/'+getpass.getuser()+'/ix -c /etc/ix.conf -- /tmp/'+getpass.getuser()+'/echoserver %d 524288' % DEF_MSG_SIZE, 'sudo kill {pid}', ignore_stdout = True)
      bench_common.wait_for_network(clients[0], bench_common.get_host_ip(server), port)
      bench_common.consume(channel)

    i = 1.4
    while i <= 5.5:
      connections_per_client = int(10**i) / len(clients)
      bench(server, clients, connections_per_client, port, len(cores), channel if args.kstats else None)
      i += 0.2

if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    pass
