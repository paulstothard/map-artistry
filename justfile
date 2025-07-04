all: edmonton-coral edmonton-river-runs-red edmonton-satellite victoria-coral victoria-river-runs-red victoria-satellite

edmonton-coral:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-coral -b 10 -w 36 -h 36 -d 600 -f png -s coral

edmonton-river-runs-red:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-river-runs-red -b 10 -w 36 -h 36 -d 600 -f png -s river_runs_red

edmonton-satellite:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-satellite -b 10 -w 36 -h 36 -d 600 -f png -s satellite -z 16

victoria-coral:
    ./map-all.sh "Victoria, BC" output/victoria-coral -b 30 -w 36 -h 36 -d 600 -f png -s coral --with-ocean

victoria-river-runs-red:
    ./map-all.sh "Victoria, BC" output/victoria-river-runs-red -b 30 -w 36 -h 36 -d 600 -f png -s river_runs_red --with-ocean

victoria-satellite:
    ./map-all.sh "Victoria, BC" output/victoria-satellite -b 30 -w 36 -h 36 -d 600 -f png -s satellite -z 16 --with-ocean