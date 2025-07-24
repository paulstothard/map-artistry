all: edmonton-coral edmonton-river-runs-red edmonton-satellite victoria-coral victoria-river-runs-red victoria-satellite

start-at-config: edmonton-coral-config edmonton-river-runs-red-config edmonton-satellite-config victoria-coral-config victoria-river-runs-red-config victoria-satellite-config

edmonton-coral:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -b 25 -w 36 -h 24 -d 600 -f png -s coral

edmonton-river-runs-red:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -b 25 -w 36 -h 24 -d 600 -f png -s river_runs_red

edmonton-satellite:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -b 25 -w 36 -h 24 -d 600 -f png -s satellite -z 15

victoria-coral:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -b 50 -w 36 -h 24 -d 600 -f png -s coral --with-ocean

victoria-river-runs-red:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -b 50 -w 36 -h 24 -d 600 -f png -s river_runs_red --with-ocean

victoria-satellite:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -b 50 -w 36 -h 24 -d 600 -f png -s satellite -z 15 --with-ocean

edmonton-coral-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -s coral -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

edmonton-river-runs-red-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

edmonton-satellite-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -z 15 -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

victoria-coral-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -s coral -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force

victoria-river-runs-red-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force

victoria-satellite-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -s satellite -z 15 -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force
