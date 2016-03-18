if (ARG1 eq 'eps') {
  set terminal postscript eps enhanced color size 5.4,3.6 font 'Times,18'
} else {
  set terminal png size 1680,1050
}
set output 'memcached-batch.'.ARG1
set style data lines
set style line 1 pointtype 4 linetype 4 pointsize .5
set style line 2 pointtype 4 linetype 3 pointsize .5
set style line 3 pointtype 4 linetype 2 pointsize .5
set style line 4 pointtype 4 linetype 1 pointsize .5
set grid y linewidth 2
set border 3
set tics out nomirror
set key left top

list = ARG2.'/ix.memcached.usr.batch1 '.ARG2.'/ix.memcached.usr.batch2 '.ARG2.'/ix.memcached.usr.batch8 '.ARG2.'/ix.memcached.usr';
batch = '1 2 8 64'
set xlabel 'USR: Throughput (RPS x 10^{6})'
set ylabel 'Latency ({/Symbol m}s)'
set xrange [0:7]
set yrange [0:750]
set ytics (0, 250, 500, 750)
set arrow from 0,500 to 6.85,500 nohead lw 1
set label 'SLA' at 6.86,500
plot for [i=1:words(list)] word(list,i) using ($12/10**6):11 linestyle i  title 'B='.word(batch, i)
