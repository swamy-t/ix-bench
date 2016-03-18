import Queue
import contextlib
import os.path
import shlex
import socket
import sys
import threading
import time
import traceback
import getpass

CLIENT_COMM_TIME_LIMIT = 0.005
WARMUP = 0

RESET = '\x1b[0m'
BOLD = '\x1b[1m'

def deploy(shell, files):
  with shell._connect_sftp() as sftp:
    for file in files:
      targetdir='/tmp/'+getpass.getuser()
      dest = os.path.join(targetdir, os.path.basename(file))
      shell.run(["mkdir", "-p", targetdir])
      sftp.put(file, dest)
      shell.run(shlex.split('chmod %o %s' % (os.stat(file).st_mode & 0777, dest)))

def get_host_ip(shell):
  ip = shell.run(shlex.split('grep host_addr /etc/ix.conf')).output
  ip = ip.split('"')[1].split('/')[0]
  return ip

def get_cores(shell):
  cores = shell.run(shlex.split('grep ^cpu /etc/ix.conf')).output
  cores = cores.split('[')[1]
  cores = cores.split(']')[0]
  cores = cores.split(',')
  cores = [x.strip() for x in cores]
  return cores

class Clients:
  def __init__(self, proc_manager, shells, cmdline, kill, duration = 5):
    self.proc_manager = proc_manager
    self.shells = shells
    self.cmdline = cmdline
    self.kill = kill
    self.duration = duration

  def run(self):
    self.channels = []
    for shell in self.shells:
      channel, pid = self.proc_manager.spawn(shell, self.cmdline, self.kill)
      self.channels.append(channel)
      channel.settimeout(5)

    self.outputs = [channel.makefile('rb') for channel in self.channels]

    try:
      return self.run_inner()
    except Exception, e:
      print >>sys.stderr, 'Exception in Clients: %r' % e
      traceback.print_exc()
      return 0

  def run_inner(self):
    for i in xrange(len(self.outputs)):
      while True:
        try:
          line = self.outputs[i].readline()
        except socket.timeout:
          line = ''
        if len(line) == 0 or line == 'ready\n':
          break
      if len(line) == 0:
        self.proc_manager.killall()
        for i in xrange(len(self.channels)):
          print >>sys.stderr, '%s: stdout: %s' % (self.shells[i]._hostname, self.outputs[i].read())
          print >>sys.stderr, '%s: stderr: %s' % (self.shells[i]._hostname, self.channels[i].makefile_stderr('rb').read())
        raise ValueError('client failed')

    before_lines, before_time = self.wait_and_sync(WARMUP)
    after_lines, after_time = self.wait_and_sync(self.duration)

    msgs = 0
    for i in xrange(len(after_lines)):
      msgs += int(after_lines[i].split()[1]) - int(before_lines[i].split()[1])

    duration = after_time - before_time

    return 1.0 * msgs / duration

  def wait_and_sync(self, wait):
    time.sleep(wait)

    for channel in self.channels:
      channel.sendall('\n')

    t = time.time()
    lines = [output.readline() for output in self.outputs]
    timestamp = time.time()
    if timestamp - t > CLIENT_COMM_TIME_LIMIT:
      print >>sys.stderr, 'Warning: synchronization of clients lasted %f ms' % ((timestamp - t) * 1000)
    return lines, timestamp

class ProcessManager:
  def __init__(self, debug = False):
    self.atexit = []
    self.threads = []
    self.debug = debug

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.killall()
    for thread in self.threads:
      thread.join()
    return False

  def killall(self):
    for shell, kill, cmdline, channel, ignore_stdout in self.atexit:
      shell.run(shlex.split(kill), allow_error = True)
      channel.status_event.wait(1)
      if not channel.exit_status_ready():
        print >>sys.stderr, 'Error: cmdline "%s" did not kill this cmdline "%s"' % (kill, cmdline)
      else:
        status = channel.recv_exit_status()
        if status != 0 and status != -1 and status != 143:
          print >>sys.stderr, '%s%s-%s-status:%s %d' % (BOLD, shell._hostname, cmdline.split()[0], RESET, status)
        if not ignore_stdout:
          data = channel.makefile('rb').read()
          if len(data) > 0:
            if data[-1] == '\n':
              data = data[:-1]
            print >>sys.stderr, '%s%s-%s-stdout:%s\n%s' % (BOLD, shell._hostname, cmdline.split()[0], RESET, data)
        data = channel.makefile_stderr('rb').read()
        if len(data) > 0:
          if data[-1] == '\n':
            data = data[:-1]
          print >>sys.stderr, '%s%s-%s-stderr:%s\n%s' % (BOLD, shell._hostname, cmdline.split()[0], RESET, data)

  def spawn(self, shell, cmdline, kill = None, cwd = None, ignore_stdout = False):
    #print >>sys.stderr, '%s%s:%s %s' % (BOLD, shell._hostname, RESET, cmdline)
    channel = shell._get_ssh_transport().open_session()
    cmd = []
    cmd.append('echo $$')
    if cwd is not None:
      cmd.append('cd %s' % cwd)
    cmd.append('exec %s' % cmdline)
    cmd = ' && '.join(cmd)
    channel.exec_command(cmd)

    pid = simple_readline(channel)
    pid = int(pid)

    if kill is not None:
      self.atexit.append((shell, kill.format(pid = pid), cmdline, channel, ignore_stdout))

    if self.debug:
      stdout = channel.makefile('rb')
      t = threading.Thread(target = _debug_print, args = (('%s-%s-stdout' % (shell._hostname, cmdline.split()[0]), stdout)))
      self.threads.append(t)
      t.start()

      stderr = channel.makefile_stderr('rb')
      t = threading.Thread(target = _debug_print, args = (('%s-%s-stderr' % (shell._hostname, cmdline.split()[0]), stderr)))
      self.threads.append(t)
      t.start()

    return channel, pid

  def run(self, shell, cmdline, cwd = None):
    channel, _ = self.spawn(shell, cmdline, cwd = cwd)
    while not channel.exit_status_ready():
      time.sleep(.1)

def _debug_print(prefix, file):
    while True:
      line = readline_retry(file)
      if len(line) == 0:
        break
      print >>sys.stderr, '%s%s:%s %s' % (BOLD, prefix, RESET, line[:-1])
    print >>sys.stderr, '%s%s: closed%s' % (BOLD, prefix, RESET)

def simple_readline(channel):
  data = []
  while True:
    byte = channel.recv(1)
    if len(byte) == 0:
      return None
    if byte == '\n':
      return ''.join(data)
    data.append(byte)

def readline_retry(f):
  while True:
    try:
      return f.readline()
    except socket.timeout:
      pass

def generator_from_file(file):
  while True:
    line = readline_retry(file)
    if len(line) == 0:
      break
    yield line

def multiplexer(*generators):
  threads = []
  queue = Queue.Queue()

  def next(id, src):
    for line in src:
      queue.put((id, line))
    queue.put((id, None))

  for i in xrange(len(generators)):
    t = threading.Thread(target = next, args = (i, generators[i]))
    threads.append(t)
    t.start()

  finished = 0
  while finished < len(generators):
    try:
      src, line = queue.get(timeout = 1)
      if line is None:
        finished += 1
      yield src, line
    except Queue.Empty:
      pass

def mutilate_benchmark(proc_manager, clients, cmdline, connections, threads, records, depth, latency_connections, latency_qps, time):
  connections_per_thread = connections / (threads * (len(clients) - 1))
  agents = ','.join([c._hostname for c in clients][1:])

  common_cmdline = '/tmp/'+getpass.getuser()+'/mutilate --binary --records=%d %s' % (records, cmdline)
  #load_cmdline = common_cmdline + ' --loadonly'
  bench_cmdline = 'timeout 600 ' + common_cmdline + ' --noload --threads=1 --depth=%d --measure_depth=1 --connections=%d --measure_connections=%d --measure_qps=%d --agent=%s --time=%d' % (depth, connections_per_thread, latency_connections, latency_qps, agents, time)

  #clients[0].run(shlex.split(load_cmdline))

  for c in clients[1:]:
    proc_manager.spawn(c, '/tmp/'+getpass.getuser()+'/mutilate --agentmode --threads %d' % (threads,), 'kill {pid}')

  proc, _ = proc_manager.spawn(clients[0], bench_cmdline, 'kill {pid}')
  proc.settimeout(1)
  mutilate = proc.makefile('rb')

  return generator_from_file(mutilate)

def wait_for_network(client, host, port):
  count = 0
  while True:
    result = client.run(shlex.split('nc -w 1 %s %d' % (host, port)), allow_error = True)
    if result.return_code == 0:
      break
    count += 1
    if count > 10:
      raise ValueError('ix failed to boot')

def consume(channel):
  # TODO: this is just a hack that reads 5 times to flush initial logs of IX
  channel.settimeout(1)
  try:
    for i in xrange(5):
      channel.makefile('rb').read()
  except socket.timeout:
    pass
