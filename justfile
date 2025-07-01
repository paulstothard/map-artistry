all: edmonton-coral edmonton-river-runs-red victoria-coral victoria-river-runs-red

edmonton-coral:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-coral -b 10 -w 36 -h 36 -d 1200 -f png -s coral

edmonton-river-runs-red:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-river-runs-red -b 10 -w 36 -h 36 -d 1200 -f png -s river_runs_red

victoria-coral:
    ./map-all.sh "Victoria, BC" output/victoria-coral -b 30 -w 36 -h 36 -d 1200 -f png -s coral

victoria-river-runs-red:
    ./map-all.sh "Victoria, BC" output/victoria-river-runs-red -b 30 -w 36 -h 36 -d 1200 -f png -s river_runs_red