if (format eq 'eps') {
  set terminal postscript eps enhanced color size width,2 font 'Times'
  unset key
  gen_title(i) = ''
} else {
  set terminal pngcairo size 1024,1024 lw 1 font 'Times'
  gen_title(i) = word(title,i)
}

set style line 1 dashtype 1     lw 1 linecolor rgbcolor 'black'
set style line 2 dashtype (2,2) lw 1 linecolor rgbcolor 'black'
set style line 3 dashtype 1     lw 1 linecolor rgbcolor 'red'
set style line 4 dashtype (2,2) lw 1 linecolor rgbcolor 'red'

set output outfile
set grid y linewidth 2
set border 3
set tics out nomirror

set lmargin 8.2
set xtics 2
set xrange [0:xmax]
set yrange [0:110]
set xlabel 'Memcached RPS x 10^{6} at SLO'
set ylabel 'Power (W)'

set key right bottom

plot pareto_ix using ($1/10**6):2 title 'Pareto IX' linestyle 3 with lines,\
     dvfs_ix using ($1/10**6):2 title 'DVFS-only IX' linestyle 4 with lines, \
     pareto_linux using ($1/10**6):2 title 'Pareto Linux' linestyle 1 with lines,\
     dvfs_linux using ($1/10**6):2 title 'DVFS-only Linux' linestyle 2 with lines
