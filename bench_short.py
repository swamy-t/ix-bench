#!/usr/bin/env python

import argparse
import getpass
import shlex
import spur
import sys

import bench_common

IX_PORT = 8000
LINUX_PORT = 9876
DEF_MSG_SIZE = 64
MSGS_PER_CONN = [2, 8, 32, 64, 128, 256, 512, 1024]
MSG_SIZES = [256, 1024, 4096, 8192]
CONNECTIONS_PER_CLIENT = 100

def bench(target, server, clients, cores, core_count, msg_size, msg_per_conn):
  result = 0

  try:
    with bench_common.ProcessManager() as proc_manager:
      if target == 'linux':
        port = LINUX_PORT
        core_str = ','.join([str(x) for x in cores[:core_count]])
        proc_manager.spawn(server, 'stdbuf -o0 -e0 /tmp/'+getpass.getuser()+'/server %d %s' % (msg_size, core_str), 'kill {pid}')
      elif target == 'ix':
        port = IX_PORT
        channel, pid = proc_manager.spawn(server, 'sudo stdbuf -o0 -e0 /tmp/'+getpass.getuser()+'/ix -c /etc/ix.conf -- /tmp/'+getpass.getuser()+'/echoserver %d' % msg_size, 'sudo kill {pid}')
        bench_common.wait_for_network(clients[0], bench_common.get_host_ip(server), port)
        proc_manager.run(server, 'sudo sh -c "rm -f /tmp/'+getpass.getuser()+'/block-*.fifo"')
        proc_manager.run(server, 'sudo /tmp/'+getpass.getuser()+'/ixcp.py --cpus %d' % core_count, cwd = '/tmp/'+getpass.getuser())
        bench_common.consume(channel)

      clients_ = bench_common.Clients(proc_manager, clients, '/tmp/'+getpass.getuser()+'/client %s %d %d %d %d' % (bench_common.get_host_ip(server), port, CONNECTIONS_PER_CLIENT, msg_size, msg_per_conn), 'kill {pid}')
      result = clients_.run()
  except Exception, e:
    print >>sys.stderr, 'Exception: %r' % e
  finally:
    print '%d %d %d %d' % (core_count, msg_size, msg_per_conn, result)

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--target', choices=['linux', 'ix'], required=True)
  parser.add_argument('--ix')
  parser.add_argument('server')
  parser.add_argument('client', nargs='+')
  args = parser.parse_args()

  server = spur.SshShell(args.server, missing_host_key = spur.ssh.MissingHostKey.accept)
  clients = []
  for client_name in args.client:
    clients.append(spur.SshShell(client_name, missing_host_key = spur.ssh.MissingHostKey.accept))

  cores = bench_common.get_cores(server)

  if args.target == 'linux':
    server_deploy = ['server']
  elif args.target == 'ix':
    server_deploy = [args.ix + '/dp/ix', args.ix + '/apps/echoserver', args.ix + '/cp/ixcp.py']
  bench_common.deploy(server, server_deploy)
  for client in clients:
    bench_common.deploy(client, ['client'])

  for core_count in xrange(1, len(cores) + 1):
    bench(args.target, server, clients, cores, core_count, DEF_MSG_SIZE, 1)

  for msg_per_conn in MSGS_PER_CONN:
    bench(args.target, server, clients, cores, len(cores), DEF_MSG_SIZE, msg_per_conn)

  for msg_size in MSG_SIZES:
    bench(args.target, server, clients, cores, len(cores), msg_size, 1)

if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    pass
