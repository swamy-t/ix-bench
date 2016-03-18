if (ARG1 eq 'eps') {
  set terminal postscript eps enhanced color size 5.4,2.2 font 'Times,18'
} else {
  set terminal png size 1680,1050
  set output 'short.'.ARG1
  set multiplot layout 1,3
}
set style data linespoints
set style line 1 pointtype 6 linecolor rgbcolor 'red'
set style line 2 pointtype 7 linecolor rgbcolor 'red'
set style line 3 pointtype 8 linecolor rgbcolor 'blue'
set style line 4 pointtype 4 linecolor rgbcolor 'black'
set style line 5 pointtype 5 linecolor rgbcolor 'black'
set grid y linewidth 2
set border 3
set tics out nomirror
unset key
list = ARG2.'/linux.10.short '.ARG2.'/linux.40.short '.ARG2.'/mtcp.short '.ARG2.'/ix.10.short '.ARG2.'/ix.40.short';

if (ARG1 eq 'eps') { set output 'short-mcore.'.ARG1 }
fig(infile) = "< awk '//{if ($2==64&&$3==1)print $0 }' ".infile.'| sort -nk1'
set xlabel 'Number of CPU cores'
set ylabel 'Messages/sec (x 10^{6})'
set xrange [0:*]
set yrange [0:*]
set xtics ('0' 0, '1' 2, '2' 4, '3' 6, '4' 8, '5' 10, '6' 12, '7' 14, '8' 16)
plot for [i=1:words(list)] fig(word(list,i)) using 1:($4/10**6) linestyle i

if (ARG1 eq 'eps') { set output 'short-roundtrips.'.ARG1 }
fig(infile) = "< export MAX=\`tail -1 ".infile."|awk '{print $1}'\`; awk '//{if ($1=='$MAX'&&$2==64)print $0 }' ".infile.'| sort -nk3'
set xlabel 'Number of Messages per Connection'
set ylabel 'Messages/sec (x 10^{6})'
set xrange [0:*]
set yrange [0:*]
set xtics ('0' 0, '1' 1, '2' 2, '8' 3, '32' 4, '64' 5, '128' 6, '256' 7, '512' 8, '1K' 9)
plot for [i=1:words(list)] fig(word(list,i)) using ($0+1):($4/10**6) linestyle i

if (ARG1 eq 'eps') { set output 'short-size.'.ARG1 }
fig(infile) = "< export MAX=\`tail -1 ".infile."|awk '{print $1}'\`; awk '//{if ($1=='$MAX'&&$3==1)print $0 }' ".infile.'| sort -nk2'
set xlabel 'Message Size'
set ylabel 'Goodput (Gbps)'
set xrange [0:*]
set yrange [0:*]
set xtics ('0' 0)
plot for [i=1:words(list)] fig(word(list,i)) using ($0+1):($2*$4*8/10**9):xticlabel(2) linestyle i

if (ARG1 eq 'eps') {
  set output 'short-key.'.ARG1
  unset border
  unset tics
  set key box horizontal left top height -0.1 width 3
  set yrange [-1:1]
  set size 1.3,.2
  unset xlabel
  unset ylabel
  plot NaN with linespoints linestyle 1 title 'Linux 10Gbps',\
       NaN with linespoints linestyle 2 title 'Linux 40Gbps',\
       NaN with linespoints linestyle 4 title 'IX 10Gbps',\
       NaN with linespoints linestyle 5 title 'IX 40Gbps',\
       NaN with linespoints linestyle 3 title 'mTCP 10Gbps'
}
