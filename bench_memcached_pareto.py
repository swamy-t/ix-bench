#!/usr/bin/env python

import getpass
import os
import argparse
import shlex
import time
import spur

import bench_common

CONNECTIONS = 2720
DEPTH = 4
IX_PORT = 8000
LINUX_PORT = 11211
LATENCY_CONNECTIONS = 32
LATENCY_QPS = 2000
RECORDS = 1000000
THREADS = 16
TIME = 300

WORKLOADS = {
  'etc': '--keysize=fb_key --valuesize=fb_value --iadist=fb_ia --update=0.033',
  'usr': '--keysize=19 --valuesize=2 --update=0.002',
}

DIR = '/tmp/' + getpass.getuser()

class Power():
  MSR_PKG_ENERGY_STATUS = 0x00000611

  def __init__(self, host, cpu):
    self.host = host
    self.cpu = cpu
    self.energy_unit = self.get_energy_unit()

  def start(self):
    self.prv_energy = self.rdmsr(self.MSR_PKG_ENERGY_STATUS)
    self.prv_time = time.time()

  def read(self):
    energy = self.rdmsr(self.MSR_PKG_ENERGY_STATUS)
    this_time = time.time()
    diff = energy - self.prv_energy
    if diff < 0:
      diff += 2 ** 32
    diff = diff / (this_time - self.prv_time)
    self.prv_energy = energy
    self.prv_time = this_time
    return diff * self.energy_unit

  def get_energy_unit(self):
    MSR_RAPL_POWER_UNIT = 0x00000606
    ENERGY_UNIT_MASK = 0x1F00
    ENERGY_UNIT_OFFSET = 0x08
    val = self.rdmsr(MSR_RAPL_POWER_UNIT)
    return 1.0 / (1 << ((val & ENERGY_UNIT_MASK) >> ENERGY_UNIT_OFFSET))

  def rdmsr(self, msr):
    val = self.host.run(shlex.split('sudo rdmsr -u -p %d %d' % (self.cpu, msr))).output[:-1]
    return int(val)

class Cores():
  def __init__(self, host, cores):
    core_list = ','.join(cores)
    self.cores = []
    for line in host.run(shlex.split('bash -c "grep -h . /sys/devices/system/cpu/cpu{%s}/topology/thread_siblings_list"' % core_list)).output.splitlines():
      pair = map(int, line.split(','))
      pair = tuple(sorted(pair))
      if pair not in self.cores:
        self.cores.append(pair)

  def output(self, clist, htlist, background):
    if background:
      blist = [x[0] for x in self.cores if x[0] not in clist and x[1] not in htlist]
      blist.sort()
    else:
      blist = []
    return clist, htlist, blist

  def all_cfgs(self, background):
    ret = []
    # spread configuration
    for i in xrange(2,len(self.cores)+1):
      clist = map(lambda x: x[0], self.cores[:i])
      ret.append(self.output(clist, [], background))
    for i in xrange(1,len(self.cores)+1):
      clist = map(lambda x: x[0], self.cores)
      htlist = map(lambda x: x[1], self.cores[:i])
      ret.append(self.output(clist, htlist, background))

    # pack configuration
    for i in xrange(1,len(self.cores)):
      clist = map(lambda x: x[0], self.cores[:i])
      htlist = map(lambda x: x[1], self.cores[:i-1])
      ret.append(self.output(clist, htlist, background))
      htlist = map(lambda x: x[1], self.cores[:i])
      ret.append(self.output(clist, htlist, background))

    if background:
      ret = filter(lambda x: len(x[2]) > 0, ret)
    ret.sort(key = lambda x: - len(x[0]) - len(x[1]))
    return ret

  def spread_list(self):
    return map(lambda x: x[0], self.cores)

def set_freq(server, freq):
  server.run(shlex.split('sudo sh -c "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo userspace > $i; done"'))
  server.run(shlex.split('sudo sh -c "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed; do echo %d > $i; done"' % freq))

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--ix')
  parser.add_argument('--target', choices=['linux', 'ix'], required=True)
  parser.add_argument('--workload', choices=WORKLOADS.keys(), required=True)
  parser.add_argument('--with-background-job', action='store_true', dest='background')
  parser.add_argument('--mutilate', required=True)
  parser.add_argument('--memcached', required=True)
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
  if args.background:
    server_deploy.append('sha1_bench')
  bench_common.deploy(server, server_deploy)
  for client in clients:
    bench_common.deploy(client, [args.mutilate])

  frequencies = server.run(shlex.split('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies')).output
  frequencies = sorted(map(int, frequencies.split()), reverse = True)

  cores = bench_common.get_cores(server)
  numa_node = int(server.run(shlex.split('cat /sys/devices/system/cpu/cpu%s/topology/physical_package_id' % cores[0])).output)

  cores_obj = Cores(server, cores)

  power = Power(server, int(cores[0]))

  if args.background:
    core_spread_list = cores_obj.spread_list()
    for freq in frequencies:
      set_freq(server, freq)
      power.start()
      sha1_thr = server.run(shlex.split('taskset -c %(cores)s %(DIR)s/sha1_bench -t 5 -T %(count)d -s 41943040' % { 'DIR': DIR, 'cores': ','.join(map(str,core_spread_list)), 'count': len(core_spread_list) })).output
      this_power = power.read()
      sha1_thr = sha1_thr.split()
      sha1_thr = sha1_thr[3]
      print 0, '00000000', freq, 0, 'read', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, this_power, sha1_thr

  for corelist, htlist, backlist in cores_obj.all_cfgs(args.background):
    for freq in frequencies:
      set_freq(server, freq)
      bench(args, server, clients, numa_node, power, freq, corelist, htlist, backlist)

def bench(args, server, clients, numa_node, power, freq, corelist, htlist, backlist):
  core_count = len(corelist)
  ht_count = len(htlist)

  corelist = sorted(corelist + htlist)
  mask = reduce(lambda x,y:x|1<<int(y),corelist,0)

  with bench_common.ProcessManager() as proc_manager:
    if args.target == 'linux':
      port = LINUX_PORT
      corelist_str = ','.join(map(str, corelist))
      proc_manager.spawn(server, 'stdbuf -o0 -e0 numactl -m %(numa_node)d %(DIR)s/memcached -k -Mm 1024 -c 4096 -b 8192 -t %(count)d -T %(cores)s' % { 'DIR': DIR, 'numa_node': numa_node, 'count': len(corelist), 'cores': corelist_str }, 'kill {pid}')
      bench_common.wait_for_network(clients[0], bench_common.get_host_ip(server), port)
    elif args.target == 'ix':
      port = IX_PORT
      channel, pid = proc_manager.spawn(server, 'sudo stdbuf -o0 -e0 %(DIR)s/ix -c /etc/ix.conf -- %(DIR)s/memcached -k -Mm 1024 -c 4096 -o hashpower=20' % { 'DIR': DIR }, 'sudo kill {pid}')
      bench_common.wait_for_network(clients[0], bench_common.get_host_ip(server), port)
      server.run(shlex.split('sudo sh -c "rm -f %(DIR)s/block-*.fifo"' % { 'DIR': DIR }))
      corelist = ','.join(map(str, corelist))
      server.run(shlex.split('sudo %(DIR)s/ixcp.py --cpulist %(cores)s' % { 'DIR': DIR, 'cores': corelist }), cwd = DIR)
      bench_common.consume(channel)

    cmdline = ' --server=%s:%d %s --report-stats=1 --qps-function=triangle:10000:15010000:600:0 --stop-latency 99:500' % (bench_common.get_host_ip(server), port, WORKLOADS[args.workload])
    mutilate = bench_common.mutilate_benchmark(proc_manager, clients, cmdline, CONNECTIONS, THREADS, RECORDS, DEPTH, LATENCY_CONNECTIONS, LATENCY_QPS, TIME)

    if args.background:
      proc, background_pid = proc_manager.spawn(server, 'stdbuf -o0 -e0 taskset -c %(cores)s %(DIR)s/sha1_bench -T %(count)d -s 41943040' % { 'DIR': DIR, 'cores': ','.join(map(str, backlist)), 'count': len(backlist) }, 'kill {pid}')
      proc.settimeout(1)
      sha1_bench = proc.makefile('rb')

    power.start()
    for line in mutilate:
      if line is None:
        break
      parts = line.split()
      if len(parts) < 2 or parts[1] != 'read':
        continue
      print '%d/%d %08x %d' % (core_count, ht_count, mask, freq),
      print line[:-1],
      if args.target == 'linux':
        print power.read(),
      elif args.target == 'ix':
        print server.run(shlex.split('sudo %(DIR)s/ixcp.py --print-power' % { 'DIR': DIR })).output[:-1],
      if args.background:
        server.run(shlex.split('kill -USR1 %d' % (background_pid,)))
        line = bench_common.readline_retry(sha1_bench)[:-1]
        parts = line.split()
        print parts[3]
      else:
        print ''

if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    pass
