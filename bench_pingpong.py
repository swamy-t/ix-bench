#!/usr/bin/env python

import argparse
import shlex
import spur
import time
import getpass

import bench_common

IX_PORT = 8000
IX_MSG_SIZES = [64, 20000, 40000, 60000, 80000, 100000, 120000, 140000, 160000, 180000, 200000, 300000, 400000, 524288]
IX_WAIT_TO_BOOT_SECS = 5

DIR = '/tmp/' + getpass.getuser()

def bench_linux(args, host1, host2):
  bench_common.deploy(host1, ['NPtcp'])
  bench_common.deploy(host2, ['NPtcp'])
  with bench_common.ProcessManager() as proc_manager:
    proc_manager.spawn(host1, 'stdbuf -o0 -e0 %(DIR)s/NPtcp -r -n 100 -p 0 -l 64 -u 1048576' % {'DIR' : DIR}, 'kill {pid}')
    host2.run(shlex.split('rm -f %(DIR)s/np.out' % {'DIR' : DIR}))
    host2.run(shlex.split('%(DIR)s/NPtcp -r -n 100 -p 0 -l 64 -u 1048576 -h %(host)s' % {'DIR' : DIR, 'host': bench_common.get_host_ip(host1)}), cwd = DIR)
    cmd = host2.run(shlex.split('cat %(DIR)s/np.out' % {'DIR' : DIR}))
    for pkt_size, goodput_mbps, _ in [[float(field) for field in line.split()] for line in cmd.output.splitlines()]:
      msg_per_sec = goodput_mbps * 1024 * 1024 / 8 / 2 / pkt_size
      print '%d %f' % (pkt_size, msg_per_sec)

def bench_ix(args, host1, host2):
  bench_common.deploy(host1, [args.ix + '/dp/ix', args.ix + '/apps/echoserver'])
  bench_common.deploy(host2, [args.ix + '/dp/ix', args.ix + '/apps/echoclient'])
  for msg_size in IX_MSG_SIZES:
    result = 0
    try:
      with bench_common.ProcessManager() as proc_manager:
        channel, pid = proc_manager.spawn(host1, 'sudo stdbuf -o0 -e0 %(DIR)s/ix -c /etc/ix.conf -- %(DIR)s/echoserver %(msg_size)d 2' % {'DIR' : DIR, 'msg_size': msg_size}, 'sudo kill {pid}')
        time.sleep(IX_WAIT_TO_BOOT_SECS)
        bench_common.consume(channel)
        clients = bench_common.Clients(proc_manager, [host2], 'sudo %(DIR)s/ix -l 0 -c /etc/ix.conf -- %(DIR)s/echoclient %(host)s %(port)d %(msg_size)d' % {'DIR' : DIR, 'host': bench_common.get_host_ip(host1), 'port': IX_PORT, 'msg_size': msg_size}, 'sudo kill {pid}')
        result = clients.run()
    finally:
      print '%d %f' % (msg_size, result)

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--target', choices=['linux', 'ix'], required=True)
  parser.add_argument('--ix')
  parser.add_argument('host1')
  parser.add_argument('host2')
  args = parser.parse_args()

  host1 = spur.SshShell(args.host1, missing_host_key = spur.ssh.MissingHostKey.accept)
  host2 = spur.SshShell(args.host2, missing_host_key = spur.ssh.MissingHostKey.accept)

  if args.target == 'linux':
    bench_linux(args, host1, host2)
  elif args.target == 'ix':
    bench_ix(args, host1, host2)

if __name__ == '__main__':
  main()
