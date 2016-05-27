if (ARG1 eq 'eps') {
  set terminal postscript eps enhanced color size 5.4,3.3 font 'Times,18'
} else {
  set terminal png size 1680,1050
}

set style data linespoints
set style line 1 pointtype 6 linecolor rgbcolor 'red'
set style line 2 pointtype 7 linecolor rgbcolor 'red'
set style line 3 pointtype 4 linecolor rgbcolor 'black'
set style line 4 pointtype 5 linecolor rgbcolor 'black'
set output 'connscaling-throughput.'.ARG1
set grid y linewidth 2
set border 3
set tics out nomirror
set key top left invert
list = ARG2.'/linux.10.connscaling '.ARG2.'/linux.40.connscaling '.ARG2.'/ix.10.connscaling '.ARG2.'/ix.40.connscaling';
titles = 'Linux-10 Linux-40 IX-10 IX-40'

set xlabel 'Connection Count (log scale)'
set ylabel 'Messages/sec (x 10^{6})'
set xrange [*:300000]
set yrange [0:*]
set logscale x
plot for [i=1:words(list)] word(list,i) using 1:($2/10**6) title word(titles, i) linestyle i
