if (format eq 'eps') {
  set terminal postscript eps enhanced color size 2.5,1.3 font 'Times'
} else {
  set terminal pngcairo size 1024,1024 lw 1 font 'Times'
  set output outfile.'.'.format
  set multiplot layout 3,1
}
unset key
set style data lines
set style line 1 dashtype 1 lw 1 linecolor rgbcolor 'black'
set style line 2 dashtype 1 lw 1 linecolor rgbcolor 'blue'
set style line 3 dashtype 1 lw 1 linecolor rgbcolor 'red'
set style line 6 dashtype 1 linecolor rgbcolor 'green' pointtype 8
set style line 7 dashtype 2 linecolor rgbcolor 'green' pointtype 9
set style line 8 dashtype 1 linecolor rgbcolor 'red' pointtype 10
set style line 9 dashtype 2 linecolor rgbcolor 'red' pointtype 11
set style line 10 linetype 3 lw 3 linecolor rgbcolor 'black'
set grid y
set border 3
set tics out nomirror
set lmargin 11
set xrange [0:240]

start=60

if (format eq 'eps') { set output outfile.'-throughput.'.format }
set ylabel 'Achieved RPS (x 10^{6})'
set yrange [0:6.5]
plot dir.'mutilate.out' using ($1-start):($12/10**6) linestyle 1 title '', \
     '<(grep up0 tmp.actions)' using ($1-start):($2/10**6) with points linestyle 6 title '', \
     '<(grep up1 tmp.actions)' using ($1-start):($2/10**6) with points linestyle 7 title '', \
     '<(grep down0 tmp.actions)' using ($1-start):($2/10**6) with points linestyle 8 title '', \
     '<(grep down1 tmp.actions)' using ($1-start):($2/10**6) with points linestyle 9 title ''

if (format eq 'eps') { set output outfile.'-latency.'.format }
if (slo) {
  set arrow from 0,500 to 211,500 nohead lw 1
  set label 'SLO' at 212,500
} else {
  set arrow from 0,500 to 240,500 nohead lw 1
}
set ylabel '99^{th} pct latency ({/Symbol m}s)'
set yrange [0:1000]
plot dir.'mutilate.out' using ($1-start):11 linestyle 1 title ''
unset arrow

set xlabel 'Time (seconds)'
if (bg) {
  if (format eq 'eps') { set output outfile.'-bg_throughput.'.format }
  set ylabel '% of peak'
  set yrange [0:100]
  plot dir.'mutilate.out' using ($1-start):(($15/3520.01)*100) linestyle 1 title 'dynamic', \
          'tmp.pareto_power' using ($1-start):($2) linestyle 3 title 'Pareto'
} else {
  if (format eq 'eps') { set output outfile.'-power.'.format }
  set ylabel 'Power (W)'
  set yrange [0:110]
  plot 'tmp.max_power' using ($1-start):($2):($2-4) with filledcurves fill solid 0.3 noborder linecolor rgbcolor 'black' linetype 1 title '',\
    dir.'mutilate.out' using ($1-start):14 linestyle 1 title '',\
    'tmp.pareto_power' using ($1-start):2 linestyle 3 title ''
}

if (format eq 'eps') {
  set output 'memcached-dynamic-power-key.'.format
  unset border
  unset tics
  set key box horizontal left top
  set yrange [-1:1]
  set size 1.5,.3
  set style line 1 linetype 1 lw 9 linecolor rgbcolor 'grey'
  set style line 2 linetype 1 lw 1 linecolor rgbcolor 'black'
  set style line 3 linetype 1 lw 1 linecolor rgbcolor 'red'
  unset xlabel
  unset ylabel
  plot NaN linestyle 1 title 'max. conf.',\
       NaN linestyle 2 title 'dynamic',\
       NaN linestyle 3 title 'Pareto'
}
