#!/bin/sh

SLOW=1200000
ALLCPUS=8/8
TURBO=2401000

filter() {
  INPUT=$1
  OUTPUT=$2
  grep -e $SLOW'$\|^$'                 $INPUT > ${OUTPUT}_slow.out
  grep -e $ALLCPUS'\|^$'               $INPUT > ${OUTPUT}_allcpus.out
  grep -e $TURBO'\|^$'                 $INPUT > ${OUTPUT}_turbo.out
  grep -v -e "$ALLCPUS\|$SLOW\|$TURBO" $INPUT > ${OUTPUT}_other.out
}

plot() {
  INPUT=$1
  OUTPUT=$2
  WIDTH=$3
  XMAX=$4
  YRANGE=$5
  KEY=$6
  YLABEL="$7"
  GNUPLOT=$8

  gnuplot \
    -e format=\'$FMT\' \
    -e lines12=\'${INPUT}_slow.out\' \
    -e linesallcpu=\'${INPUT}_allcpus.out\' \
    -e linesoth=\'${INPUT}_other.out\' \
    -e linesturbo=\'${INPUT}_turbo.out\' \
    -e outfile=\'${OUTPUT}\' \
    -e pareto=\'${INPUT}_pareto.out\' \
    -e width=\'$WIDTH\' \
    -e xmax=\'$XMAX\' \
    -e key=\'$KEY\' \
    -e yrange=\'$YRANGE\' \
    -e ylabel=\'"$YLABEL"\' \
    $GNUPLOT
}

set -e

DIR=`dirname $0`
FMT=$1
RESULTS=$2

$DIR/preproc.py $RESULTS/linux.memcached.pareto.eff  . pareto_eff_linux       30000 vertical=true
$DIR/preproc.py $RESULTS/linux.memcached.pareto.back . pareto_back_linux      30000 vertical=false $RESULTS/linux.memcached.pareto.eff
$DIR/preproc.py $RESULTS/ix.memcached.pareto.eff     . pareto_eff_ix          30000 vertical=true
$DIR/preproc.py $RESULTS/ix.memcached.pareto.back    . pareto_back_ix         30000 vertical=false $RESULTS/ix.memcached.pareto.eff
$DIR/preproc.py $RESULTS/linux.memcached.pareto.eff  . pareto_core_dvfs_linux 30000 vertical=true
$DIR/preproc.py $RESULTS/ix.memcached.pareto.eff     . pareto_core_dvfs_ix    30000 vertical=true

filter pareto_eff_linux_lines.out  pareto_eff_linux
filter pareto_eff_ix_lines.out     pareto_eff_ix
filter pareto_back_linux_lines.out pareto_back_linux
filter pareto_back_ix_lines.out    pareto_back_ix

plot pareto_eff_linux  pareto-eff-linux.$FMT  1.60 2 110 0 'Power (W)' $DIR/plot_pareto_multicolor.gnuplot
plot pareto_eff_ix     pareto-eff-ix.$FMT     4.50 8 110 1 '' $DIR/plot_pareto_multicolor.gnuplot
plot pareto_back_linux pareto-back-linux.$FMT 1.60 2 100 0 '% of Peak for Best-effort Task' $DIR/plot_pareto_multicolor.gnuplot
plot pareto_back_ix    pareto-back-ix.$FMT    4.50 8 100 0 '' $DIR/plot_pareto_multicolor.gnuplot

gnuplot \
  -e dvfs_ix=\'pareto_core_dvfs_ix_dvfs.out\' \
  -e dvfs_linux=\'pareto_core_dvfs_linux_dvfs.out\' \
  -e format=\'$FMT\' \
  -e outfile=\'pareto-core-dvfs-both.$FMT\' \
  -e pareto_ix=\'pareto_core_dvfs_ix_pareto.out\' \
  -e pareto_linux=\'pareto_core_dvfs_linux_pareto.out\' \
  -e width='3.2' \
  -e xmax='8' \
  $DIR/plot_pareto_core_dvfs.gnuplot

$DIR/plot_memcached_dynamic.py $FMT $RESULTS

rm -f *.out
