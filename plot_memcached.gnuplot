if (ARG1 eq 'eps') {
  set terminal postscript eps enhanced color size 5.4,2.6 font 'Times,18'
} else {
  set terminal png size 1680,1050
  set output 'memcached.'.ARG1
  set multiplot layout 1,2
}
set style data lines
set style line 1 pointtype 6 dashtype 2 pointsize .5 linecolor rgbcolor 'red'
set style line 2 pointtype 4 dashtype 2 pointsize .5 linecolor rgbcolor 'black'
set style line 3 pointtype 6 dashtype 1 pointsize .5 linecolor rgbcolor 'red'
set style line 4 pointtype 4 dashtype 1 pointsize .5 linecolor rgbcolor 'black'
set grid y linewidth 2
set border 3
set tics out nomirror
unset key

if (ARG1 eq 'eps') { set output 'memcached-etc-basic.'.ARG1 }
list = ARG2.'/linux.memcached.etc '.ARG2.'/ix.memcached.etc ';
set xlabel 'ETC: Throughput (RPS x 10^{6})'
set ylabel 'Latency ({/Symbol m}s)'
set xrange [0:7]
set yrange [0:750]
set ytics (0, 250, 500, 750)
set arrow from 0,500 to 6.65,500 nohead lw 1
set label 'SLA' at 6.66,500
plot for [i=1:words(list)] word(list,i) using ($12/10**6):11 linestyle i+2, \
     for [i=1:words(list)] word(list,i) using ($12/10**6):3 linestyle i

if (ARG1 eq 'eps') { set output 'memcached-usr-basic.'.ARG1 }
list = ARG2.'/linux.memcached.usr '.ARG2.'/ix.memcached.usr';
nplots = words(list)
set xlabel 'USR: Throughput (RPS x 10^{6})'
plot for [i=1:words(list)] word(list,i) using ($12/10**6):11 linestyle i+2, \
     for [i=1:words(list)] word(list,i) using ($12/10**6):3 linestyle i

if (ARG1 eq 'eps') {
  set output 'memcached-key.'.ARG1
  unset border
  unset tics
  set key box horizontal center top height 0.3 width -5
  set yrange [-1:1]
  set size 1.2,.2
  unset xlabel
  unset ylabel
  plot NaN with lines linestyle 1 title 'Linux (avg)',\
       NaN with lines linestyle 3 title 'Linux (99^{th} pct)',\
       NaN with lines linestyle 2 title 'IX (avg)',\
       NaN with lines linestyle 4 title 'IX (99^{th} pct)'
}
