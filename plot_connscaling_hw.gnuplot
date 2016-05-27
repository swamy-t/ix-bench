if (ARG1 eq 'eps') {
  set terminal postscript eps enhanced color size 5.4,3.3 font 'Times,18'
} else {
  set terminal png size 1680,1050
}

set style data linespoints
set style line 1 linecolor rgbcolor 'red'
set style line 2 linecolor rgbcolor 'blue'
set style line 3 linecolor rgbcolor 'black'
set output 'connscaling-hw.'.ARG1
set grid y linewidth 2
set border 11
set tics out nomirror
set key top left
set xrange [*:300000]
set yrange [0:12]
set y2range [0:80]
set y2tics
set logscale x
set xlabel 'Connection Count (log scale)'
set ylabel 'cycles per msg (x 10^{3})'
set y2label 'avg. batch size / L3 misses per msg'
plot ARG2.'/ix.40.connscaling.kstats' using 1:5 axes x1y2 title 'avg. batch size' linestyle 3, \
     ''     using 1:($3/10**3) title 'cycles per msg' linestyle 1, \
     ''     using 1:4 axes x1y2 title 'L3 misses per msg' linestyle 2
