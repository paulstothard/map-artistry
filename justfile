all: edmonton-coral edmonton-river-runs-red edmonton-satellite victoria-coral victoria-river-runs-red victoria-satellite

start-at-config: edmonton-coral-config edmonton-river-runs-red-config edmonton-satellite-config victoria-coral-config victoria-river-runs-red-config victoria-satellite-config

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

edmonton-coral-config:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-coral -s coral --force -t config,map -b 10 -w 36 -h 36 -d 600 -f png

edmonton-river-runs-red-config:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red --force -t config,map -b 10 -w 36 -h 36 -d 600 -f png

edmonton-satellite-config:
    ./map-all.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -z 16 --force -t config,map -b 10 -w 36 -h 36 -d 600 -f png

victoria-coral-config:
    ./map-all.sh "Victoria, BC" output/victoria-coral -s coral --force -t config,map -b 30 -w 36 -h 36 -d 600 -f png --with-ocean

victoria-river-runs-red-config:
    ./map-all.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red --force -t config,map -b 30 -w 36 -h 36 -d 600 -f png --with-ocean

victoria-satellite-config:
    ./map-all.sh "Victoria, BC" output/victoria-satellite -s satellite -z 16 --force -t config,map -b 30 -w 36 -h 36 -d 600 -f png --with-ocean
