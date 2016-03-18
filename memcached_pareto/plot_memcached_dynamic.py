#!/usr/bin/env python

import os
import subprocess
import sys

class SafeList():
  def __init__(self, list):
    self.list = list

  def __len__(self):
    return len(self.list)

  def __getitem__(self, pos):
    if pos < len(self.list):
      return self.list[pos]
    else:
      return 0.0

  def __setitem__(self, pos, value):
    self.list[pos] = value

  def __repr__(self):
    return '%r' % self.list

def parse(file):
  f = open(file)
  for line in f:
    line = SafeList(line.split())
    for i in xrange(len(line)):
      try:
        line[i] = int(line[i])
      except:
        try:
          line[i] = float(line[i])
        except:
          pass
    yield line
  f.close()

def filter(*args):
  for row in args[-1]:
    yes = True
    for f in args[:-1]:
      if not f(row):
        yes = False
        break
    if yes:
      yield row

def fields(*args):
  for row in args[-1]:
    yield map(lambda i: row[i] if i < len(row) else 0, args[:-1])

def interpolate(x0, y0, x1, y1, x):
  return (x-x0)*(y1-y0)/(x1-x0)+y0

def list_interpolate(x, list, x_field, y_field):
  for i in xrange(len(list)):
    if x < list[i][x_field]:
      break
  prv = list[i-1]
  next = list[i]
  return interpolate(prv[x_field], prv[y_field], next[x_field], next[y_field], x)

def avg(list):
  return sum(list) / len(list)

def diff_perc(list, i, j):
  return 100.0 * (list[i] - list[j]) / list[j]

def perc(list, i, j):
  return 100.0 * list[i] / list[j]

def write_file(filename, rows):
  f = open(filename, 'w')
  for row in rows:
    for field in row:
      f.write('%s ' % field)
    f.write('\n')
  f.close()

def energy_proportionality_power(inpdir, load_pattern):
  pareto_thr_pow = fields(0, 1, parse('./pareto_eff_ix_pareto.out'))
  pareto_thr_pow = list(pareto_thr_pow)
  pareto_thr_pow = [[0, pareto_thr_pow[0][1]]] + pareto_thr_pow
  max_thr_pow = list(fields(14, 16, filter(lambda row: row[0] == "8/8" and row[2] == 2401000, parse(inpdir+'/ix.memcached.pareto.eff'))))
  curve_pareto = []
  curve_measured = []
  curve_max = []
  for row in filter(lambda row: row[1] == 'read', parse(inpdir+'/memcached-dynamic/IX-%s/mutilate.out' % load_pattern)):
    curve_pareto.append([row[0], list_interpolate(row[11], pareto_thr_pow, 0, 1)])
    curve_measured.append([row[0], row[13]])
    curve_max.append([row[0], list_interpolate(row[11], max_thr_pow, 0, 1)])
  return curve_pareto, curve_measured, curve_max

def consolidation_sha1_throughput(inpdir, load_pattern):
  for row in filter(lambda row: row[0] != '#', parse(inpdir+'/ix.memcached.pareto.back')):
    if row[0] == 0 and row[2] == 2400000:
      max_sha1 = row[17]
      break

  pareto_thr_pow = fields(0, 1, parse('./pareto_back_ix_pareto.out'))
  pareto_thr_pow = list(pareto_thr_pow)
  pareto_thr_pow = [[0, pareto_thr_pow[0][1]]] + pareto_thr_pow
  curve_pareto = []
  curve_measured = []
  for row in filter(lambda row: row[1] == 'read', parse(inpdir+'/memcached-dynamic/IX-%s-bg/mutilate.out' % load_pattern)):
    curve_pareto.append([row[0], list_interpolate(row[11], pareto_thr_pow, 0, 1)])
    curve_measured.append([row[0], (row[14]/max_sha1)*100])

  return curve_pareto, curve_measured

def actions(inpdir, load_pattern):
  curve = fields(0, 11, filter(lambda row: row[1] == 'read', parse(inpdir+'/memcached-dynamic/IX-%s/mutilate.out' % load_pattern)))
  curve = list(curve)
  f = open(inpdir+'/memcached-dynamic/IX-%s/mutilate.out' % load_pattern)
  start_time = float(f.readline().split()[3])
  f.close()
  ret = []
  prv = ''
  for row in filter(lambda row: row[2] == 'control_action', parse(inpdir+'/memcached-dynamic/IX-%s/ixcp.out' % load_pattern)):
    x = row[1] - start_time
    y = list_interpolate(x, curve, 0, 1)
    ret.append([x, y, row[3] + ('1' if row[6] != prv and not prv == '' else '0')])
    prv = row[6]
  return ret

def main():
  dirname = os.path.dirname(sys.argv[0])
  fmt = sys.argv[1]
  inpdir = sys.argv[2]

  avg_power = {}
  avg_sha1 = {}
  for load in ['triangle', 'qtriangle', 'sin_noise']:
    slo = 1 if load == 'qtriangle' else 0
    curve_pareto, curve_measured, curve_max = energy_proportionality_power(inpdir, load)
    avg_power[load] = map(avg, map(lambda curve: [row[1] for row in curve], [curve_pareto, curve_measured, curve_max]))
    write_file('tmp.pareto_power', curve_pareto)
    write_file('tmp.max_power', curve_max)
    write_file('tmp.actions', actions(inpdir, load))
    cmd = 'gnuplot -e slo=%(slo)d -e bg=0 -e format=\'"'+fmt+'"\' -e dir=\'"'+inpdir+'/memcached-dynamic/IX-%(load)s/"\' -e outfile=\'"memcached-dynamic-%(load)s"\' '+dirname+'/plot_memcached_dynamic.gnuplot'
    cmd = cmd % {'load': load, 'slo': slo}
    subprocess.call(cmd, shell=True)
    os.remove('tmp.pareto_power')
    os.remove('tmp.max_power')
    os.remove('tmp.actions')

    curve_pareto, curve_measured = consolidation_sha1_throughput(inpdir, load)
    avg_sha1[load] = map(avg, map(lambda curve: [row[1] for row in curve], [curve_pareto, curve_measured]))
    write_file('tmp.pareto_power', curve_pareto)
    write_file('tmp.actions', actions(inpdir, load + '-bg'))
    cmd = 'gnuplot -e slo=%(slo)d -e bg=1 -e format=\'"'+fmt+'"\' -e dir=\'"'+inpdir+'/memcached-dynamic/IX-%(load)s-bg/"\' -e outfile=\'"memcached-dynamic-%(load)s-bg"\' '+dirname+'/plot_memcached_dynamic.gnuplot'
    cmd = cmd % {'load': load, 'slo': slo}
    subprocess.call(cmd, shell=True)
    os.remove('tmp.pareto_power')
    os.remove('tmp.actions')

  print '             Smooth          Step          Sine+noise'
  print '-----------------------------------------------------'
  print 'Energy Proportionality (W)'
  print '-----------------------------------------------------'
  print 'Max. power   %6.0f        %6.0f        %6.0f' % (avg_power['triangle'][2], avg_power['qtriangle'][2], avg_power['sin_noise'][2])
  print 'Measured     %6.0f (%3.0f%%) %6.0f (%3.0f%%) %6.0f (%3.0f%%)' % (avg_power['triangle'][1], diff_perc(avg_power['triangle'], 1, 2), avg_power['qtriangle'][1], diff_perc(avg_power['qtriangle'], 1, 2), avg_power['sin_noise'][1], diff_perc(avg_power['sin_noise'], 1, 2))
  print 'Pareto bound %6.0f (%3.0f%%) %6.0f (%3.0f%%) %6.0f (%3.0f%%)' % (avg_power['triangle'][0], diff_perc(avg_power['triangle'], 0, 2), avg_power['qtriangle'][0], diff_perc(avg_power['qtriangle'], 0, 2), avg_power['sin_noise'][0], diff_perc(avg_power['sin_noise'], 0, 2))
  print '-----------------------------------------------------'
  print r"Server consolidation opportunity (% of peak)"
  print '-----------------------------------------------------'
  print 'Pareto bound %6.0f        %6.0f        %6.0f' % (avg_sha1['triangle'][0], avg_sha1['qtriangle'][0], avg_sha1['sin_noise'][0])
  print 'Measured     %6.0f        %6.0f        %6.0f' % (avg_sha1['triangle'][1], avg_sha1['qtriangle'][1], avg_sha1['sin_noise'][1])

  print '\033[32mupdate tbl-powersavings.tex\033[0m'
  print r'Max. power   & %.0f & %.0f & %.0f\\' % (avg_power['triangle'][2], avg_power['qtriangle'][2], avg_power['sin_noise'][2])
  print r'Measured     & %.0f (%.0f\%%) & %.0f (%.0f\%%) & %.0f (%.0f\%%)\\' % (avg_power['triangle'][1], diff_perc(avg_power['triangle'], 1, 2), avg_power['qtriangle'][1], diff_perc(avg_power['qtriangle'], 1, 2), avg_power['sin_noise'][1], diff_perc(avg_power['sin_noise'], 1, 2))
  print r'Pareto bound & %.0f (%.0f\%%) & %.0f (%.0f\%%) & %.0f (%.0f\%%)\\' % (avg_power['triangle'][0], diff_perc(avg_power['triangle'], 0, 2), avg_power['qtriangle'][0], diff_perc(avg_power['qtriangle'], 0, 2), avg_power['sin_noise'][0], diff_perc(avg_power['sin_noise'], 0, 2))
  print
  print r'Pareto bound & %.0f\%% & %.0f\%% & %.0f\%% \\' % (avg_sha1['triangle'][0], avg_sha1['qtriangle'][0], avg_sha1['sin_noise'][0])
  print r'Measured     & %.0f\%% & %.0f\%% & %.0f\%% \\' % (avg_sha1['triangle'][1], avg_sha1['qtriangle'][1], avg_sha1['sin_noise'][1])

  print '\033[32mupdate harddata.tex\033[0m'
  l = [-diff_perc(avg_power['triangle'], 0, 2), -diff_perc(avg_power['qtriangle'], 0, 2), -diff_perc(avg_power['sin_noise'], 0, 2)]
  print r'\newcommand{\dataDynSavedParetoPower}{%.0f\%%, %.0f\%% and %.0f\%%\xspace}' % tuple(sorted(l))
  l = [-diff_perc(avg_power['triangle'], 1, 2), -diff_perc(avg_power['qtriangle'], 1, 2), -diff_perc(avg_power['sin_noise'], 1, 2)]
  print r'\newcommand{\dataDynSavedMeasuredPower}{%.0f\%%, %.0f\%% and %.0f\%%\xspace}' % tuple(sorted(l))
  print r'\newcommand{\dataDynSavedRange}{%.0f\%%--%.0f\%%\xspace}' % (min(l), max(l))

  l = []
  for load in ['triangle', 'qtriangle', 'sin_noise']:
    v = 100 * (avg_power[load][2] - avg_power[load][1]) / (avg_power[load][2] - avg_power[load][0])
    l.append(v)
  print r'\newcommand{\dataDynRelativePowerSavings}{%.0f\%%, %.0f\%% and %.0f\%%\xspace}' % tuple(sorted(l))
  print r'\newcommand{\dataDynRelativeRange}{%.0f\%%--%.0f\%%\xspace}' % (min(l), max(l))
  print r'\newcommand{\dataDynRoundPowerSavings}{%.0f\%%\xspace}' % avg(l)
  print
  l = [avg_sha1['triangle'][1], avg_sha1['qtriangle'][1], avg_sha1['sin_noise'][1]]
  print r'\newcommand{\dataBackMeasuredGain}{%.0f\%%--%.0f\%%\xspace}' % (min(l), max(l))

  l = []
  for load in ['triangle', 'qtriangle', 'sin_noise']:
    v = 100 * avg_sha1[load][1] / avg_sha1[load][0]
    l.append(v)
  print r'\newcommand{\dataBackRelativeGain}{%.0f\%%--%.0f\%%\xspace}' % (min(l), max(l))

if __name__ == '__main__':
  main()
