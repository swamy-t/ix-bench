if (ARG1 eq 'eps') {
  set terminal postscript eps enhanced color size 5.4,3.6 font 'Times,18'
} else {
  set terminal png size 1680,1050
}
set style data linespoints
set style line 1 pointtype 8 linecolor rgbcolor 'blue'
set style line 2 pointtype 6 linecolor rgbcolor 'red'
set style line 3 pointtype 4 linecolor rgbcolor 'black'
set output 'pingpong.'.ARG1
set grid y linewidth 2
set border 3
set tics out nomirror
set key bottom right invert
list = ARG2.'/mtcp.pingpong '.ARG2.'/linux.pingpong '.ARG2.'/ix.pingpong'

set xlabel 'Message Size (KB)'
set ylabel 'Goodput (Gbps)'
set xrange [0:512]
set yrange [0:10]
plot for [i=1:words(list)] word(list,i) using ($1/1024):(2*$2*$1*8/10**9) title word('mTCP-mTCP Linux-Linux IX-IX', i) linestyle i
