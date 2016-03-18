#!/usr/bin/env python

import sys
import re

def main():
  if len(sys.argv) < 3:
    print 'Not enough arguments: python atc15_figures_1_3.py inputfile outputdir figure_name min_RPS vertical={true|false} [inputfile_eff]'
    return

  inputfile = sys.argv[1]
  outputdir = sys.argv[2]
  figure_name = sys.argv[3]
  if figure_name.startswith('pareto_eff'):
    mode = 'min'
  elif figure_name.startswith('pareto_back'):
    mode = 'max'
  elif figure_name.startswith('pareto_core'):
    mode = 'min'
  else:
    print 'Wrong figure name ' + figure_name
    return

  min_RPS = float(sys.argv[4])
  vertical = sys.argv[5] == 'vertical=True' or sys.argv[5] == 'vertical=true'
  inputfile_eff = None
  if figure_name.startswith('pareto_back'):
    inputfile_eff = sys.argv[6]

  if 'ix' in inputfile.lower():
    os = 'IX'
  elif 'linux' in inputfile.lower():
    os = 'Linux'
  else:
    print 'Error input file ' + inputfile
    return

  if figure_name.startswith('pareto_core'):
    paretof = find_pareto_opt_front(inputfile, outputdir, 'pareto', mode, vertical, min_RPS, False, figure_name)
    dvfs_paretof = find_pareto_opt_front(inputfile, outputdir, 'dvfs', mode, vertical, min_RPS, False, figure_name)
    write_frontier(outputdir + '/' + figure_name + '_pareto.out', paretof, False)
    write_frontier(outputdir + '/' + figure_name + '_dvfs.out', dvfs_paretof, False)
  else:
    #print "Figure = " + figure_name
    paretof = find_pareto_opt_front(inputfile, outputdir, 'pareto', mode, vertical, min_RPS, True, figure_name, inputfile_eff)
    if figure_name.startswith('pareto_eff'):
      write_frontier(outputdir + '/' + figure_name + '_pareto.out', paretof, False)
    if figure_name.startswith('pareto_back'):
      for line in open(inputfile, 'r'):
        if line.startswith('#'):
          continue
        split_line = line.split()
        if split_line[0] == '0' and split_line[2] == '2400000':
          max_sha1 = float(split_line[17])
          break
      write_frontier(outputdir + '/' + figure_name + '_pareto.out', paretof, True, max_sha1)

def find_pareto_opt_front(inputfile, outputdir, curve_type, mode, vertical, min_RPS, plot_lines, fig, inputfile_eff = None):
  dict_entries = {}
  paretof = []
  total_configs = set()

  with open(inputfile) as f:
    for line in f:
      if line.startswith('#'):
        continue
      split_line = line.split()
      if fig.startswith('pareto_back') and split_line[0] == '0' and split_line[2] == '2400000':
        max_sha1 = float(split_line[17])
      configuration = split_line[0] + "_" + split_line[2]
      rps = float(split_line[14])
      if fig.startswith('pareto_back'):
        y_axis = float(split_line[17])
      elif fig.startswith('pareto_eff') or fig.startswith('pareto_core'):
        y_axis = float(split_line[16])
      else:
        print 'Error'
        return
      if fig.startswith('pareto_back'):
        if not check_config_back(configuration):
          continue
      else:
        if not check_config_eff(configuration):
          continue

      total_configs.add(configuration)
      if curve_type == 'dvfs':
        if not check_config_dvfs(configuration):
          continue
      if configuration not in dict_entries:
        dict_entries[configuration] = [[configuration, rps, y_axis]]
      else:
        dict_entries[configuration].append([configuration, rps, y_axis])

  for key in dict_entries.keys():
    dict_entries[key].sort(key = lambda ll: ll[1])
  model_configurations = set()
  dvfs_configurations = set()
  for conf in dict_entries.keys():
    for sample in dict_entries[conf]:
      if sample[1] < min_RPS:
        continue
      in_front = True
      for cf in dict_entries.keys():
        if cf == conf:
          continue
        if dict_entries[cf][len(dict_entries[cf])-1][1] < sample[1]:
          continue
        left_index, left_neighbor = find_closest_neighbor(dict_entries[cf], sample, 'left')
        right_index, right_neighbor = find_closest_neighbor(dict_entries[cf], sample, 'right')
        if left_index == -1 or right_index == -2:
          continue
        elif left_neighbor[1] == sample[1]: #same rps
          if right_neighbor[1] != sample[1] or right_index != left_index:
            print 'Erorr neighbor'
            return
          power_cmp = left_neighbor[2]
        else:
          power_cmp = get_y_line(left_neighbor[1], left_neighbor[2], right_neighbor[1], right_neighbor[2], sample[1])
        if mode == 'min':
          if power_cmp <= sample[2]: #less or less equals?
            in_front = False
            break
          else:
            continue
        else:
          if power_cmp >= sample[2]: #gr or gr equals?
            in_front = False
            break
          else:
            continue
      if(in_front):
        paretof.append(sample)

  chosen_configs = set()
  for p in paretof:
    chosen_configs.add(p[0])
  #print 'Number of contributing configurations to ' + fig, len(chosen_configs)
  #print sorted(chosen_configs)
  #print 'Number of total configurations in ' + fig, len(total_configs)

  if vertical:
    fronts_jumps_added = set()
    for chosen_front in chosen_configs:
      new_pareto_sample = find_closest_edge(chosen_front, chosen_configs, dict_entries, mode)
      if new_pareto_sample is None:
        continue
      elif new_pareto_sample[0] in fronts_jumps_added:
        continue
      else:
        paretof.append(new_pareto_sample)
        fronts_jumps_added.add(new_pareto_sample[0])

  if plot_lines:
    for chosen_front in chosen_configs:
      if fig.startswith('pareto_back'):
        write_frontier(outputdir +'/' + fig + '_lines.out', dict_entries[chosen_front], True, max_sha1)
      else:
        write_frontier(outputdir +'/' + fig + '_lines.out', dict_entries[chosen_front], False)

  paretof.sort(key = lambda ll: ll[1])
  #MAX CONFIGURATION
  if fig.startswith('pareto_core_dvfs_ix') and curve_type == 'pareto':
    max_static_conf = paretof[-1][0]
    write_frontier(outputdir +'/' + fig + '_maxconf.out', dict_entries[max_static_conf], False)

  if fig == 'pareto_back_ix' or fig == 'pareto_back_linux':
    max_x = paretof[-1][1]
    paretof.append(['conf', max_x, 0])
    max_x = None
    if fig.endswith('linux'):
      for line in open(inputfile_eff, 'r'):
        if line.startswith('#'):
          continue
        split_line = line.split()
        if max_x is not None and float(split_line[13]) >= 500:
          break
        if split_line[0] == '8/0' and split_line[2] == '2401000':
          max_x = float(split_line[14])
      paretof.append(['conf', max_x, 0])
    elif fig.endswith('ix'):
      for line in open(inputfile_eff, 'r'):
        if line.startswith('#'):
          continue
        split_line = line.split()
        if max_x is not None and float(split_line[13]) >= 500:
          break
        if split_line[0] == '8/8' and split_line[2] == '2401000':
          max_x = float(split_line[14])
      paretof.append(['conf', max_x, 0])
  return paretof

def find_closest_edge(current_front, chosen_configs, dict_entries, mode):
  closest_edge_x = -1
  closest_edge_y = -1
  closest_conf = None
  x_edge = dict_entries[current_front][len(dict_entries[current_front]) - 1][1]
  y_edge = dict_entries[current_front][len(dict_entries[current_front]) - 1][2]

  for cc in chosen_configs:
    if cc == current_front:
      continue
    x_edge_cc = dict_entries[cc][len(dict_entries[cc]) - 1][1]
    y_edge_cc = dict_entries[cc][len(dict_entries[cc]) - 1][2]
    if x_edge_cc <= x_edge or mode == 'min' and y_edge_cc <= y_edge or mode == 'max' and y_edge_cc >= y_edge:
      continue
    if closest_edge_x == -1 or x_edge_cc < closest_edge_x:
      if closest_edge_y == -1 or mode == 'min' and y_edge_cc < closest_edge_y or mode == 'max' and y_edge_cc > closest_edge_y:
        closest_conf = cc
        closest_edge_x = x_edge_cc
        closest_edge_y = y_edge_cc

  if closest_conf is None:
    return None

  left_index, left_neighbor = find_closest_neighbor(dict_entries[closest_conf], [current_front, x_edge, y_edge], 'left')
  right_index, right_neighbor = find_closest_neighbor(dict_entries[closest_conf], [current_front, x_edge, y_edge], 'right')
  new_y = get_y_line(left_neighbor[1], left_neighbor[2], right_neighbor[1], right_neighbor[2], x_edge)

  return [closest_conf, x_edge, new_y]

def find_closest_neighbor(frontier, x, side):
  cnt = 0
  for pareto_sample in frontier:
    if pareto_sample[1] == x[1]:
      return[cnt, pareto_sample]
    elif pareto_sample[1] > x[1]:
      if side == 'left':
        return [cnt-1, frontier[cnt-1]]
      else:
        return [cnt, pareto_sample]
    else:
      cnt = cnt + 1
    first = False
  if cnt != len(frontier):
    print ('cnt ', cnt, ' len ', len(frontier))
    print 'Erorr in find_closest_neighbor'
    return[None, None]
  return [-2, None]

def check_config_eff(config):
  return re.match('[1-8]/0_', config) or config.startswith('8/8') or  config.startswith('7/7') or config.startswith('6/6')  or config.startswith('5/5') or config.startswith('4/4') or config.startswith('3/3') or config.startswith('2/2') or config.startswith('1/1')

def check_config_back(config):
  confs = ['1/0_2400000','1/1_2400000', '2/0_2400000','2/2_2400000','3/0_2400000','3/3_2400000','4/0_2400000','4/4_2400000','5/0_2400000','5/5_2400000','6/0_2400000','6/6_2400000','7/0_2400000','7/7_2400000','8/0_2400000','8/8_2400000']
  return config in confs

def check_config_dvfs(config):
  return config.startswith('8/8')

def get_y_line(x1, y1, x2, y2, xt):
  k = (y2 - y1)/(x2 - x1)
  l = (y1*x2 - y2*x1)/(x2 - x1)
  return k * xt + l

def write_frontier(filename, frontier, normalize, divisor = 0):
  with open(filename, "a") as f:
    for entry in frontier:
      if normalize:
        f.write(str(entry[1]) + " " +str((entry[2]/divisor)*100) + " " + str(entry[0])  + "\n")
      else:
        f.write(str(entry[1]) + " " +str(entry[2]) + " " + str(entry[0])  + "\n")
    f.write("\n")

if __name__ == '__main__':
  main()
