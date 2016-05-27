if (format eq 'eps') {
  set terminal postscript eps enhanced color size 5.4,2 font 'Times'
  unset key
  gen_title(i) = ''
} else {
  set terminal pngcairo size 1024,1024 lw 1 font 'Times'
  gen_title(i) = word(title,i)
}
set style data linespoints
set style line 1 linetype 1 linecolor rgbcolor 'black' #other
set style line 2 linetype 1 lw 2 linecolor rgbcolor 'red' #pareto
set style line 3 linetype 1 linecolor rgbcolor 'green' #1200000
set style line 4 linetype 1 linecolor rgbcolor 'blue' #8/8
set style line 5 linetype 1 linecolor rgbcolor 'orange' #8/0
set output outfile
set grid y linewidth 2
set border 3
set tics out nomirror

set xtics 2
set xrange [0:xmax]
set yrange [0:yrange]
set xlabel 'Memcached RPS x 10^{6} at SLO'
if (strlen(ylabel) > 0) {
	set ylabel ylabel
}
if (key) {
	set key bottom right invert
}

plot linesoth using ($1/10**6):2 title 'cfg - all others' linestyle 1 with lines, \
     linesturbo using ($1/10**6):($2):($2-4) with filledcurves fill solid 0.2 noborder linecolor rgbcolor 'black' title 'cfg at Turbo mode', \
     linesallcpu using ($1/10**6):2 title 'cfg w/ 8 cores + HT' linestyle 4 with lines, \
     lines12 using ($1/10**6):2 title 'cfg at 1.2 GHz' linestyle 3 with lines, \
     pareto using ($1/10**6):2 title 'Pareto frontier' linestyle 2 with lines
