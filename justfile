all: edmonton-coral edmonton-river-runs-red edmonton-satellite victoria-coral victoria-river-runs-red victoria-satellite edmonton-dusk victoria-dusk edmonton-night victoria-night

start-at-config: edmonton-coral-config edmonton-river-runs-red-config edmonton-satellite-config victoria-coral-config victoria-river-runs-red-config victoria-satellite-config edmonton-dusk-config victoria-dusk-config edmonton-night-config victoria-night-config

edmonton-coral:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -b 25 -w 36 -h 24 -d 600 -f png -s coral

edmonton-river-runs-red:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -b 25 -w 36 -h 24 -d 600 -f png -s river_runs_red

edmonton-satellite:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -b 25 -w 36 -h 24 -d 600 -f png -s satellite -z 15

edmonton-dusk:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-dusk -b 25 -w 36 -h 24 -d 600 -f png -s dusk

edmonton-night:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-night -b 25 -w 36 -h 24 -d 600 -f png -s night

victoria-coral:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -b 50 -w 36 -h 24 -d 600 -f png -s coral --with-ocean

victoria-river-runs-red:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -b 50 -w 36 -h 24 -d 600 -f png -s river_runs_red --with-ocean

victoria-satellite:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -b 50 -w 36 -h 24 -d 600 -f png -s satellite -z 15 --with-ocean

victoria-dusk:
    ./map-pipeline.sh "Victoria, BC" output/victoria-dusk -b 50 -w 36 -h 24 -d 600 -f png -s dusk --with-ocean

victoria-night:
    ./map-pipeline.sh "Victoria, BC" output/victoria-night -b 50 -w 36 -h 24 -d 600 -f png -s night --with-ocean

edmonton-coral-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -s coral -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

edmonton-river-runs-red-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

edmonton-satellite-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -z 15 -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

edmonton-dusk-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-dusk -s dusk -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

edmonton-night-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-night -s night -t config,map -b 25 -w 36 -h 24 -d 600 -f png --force

victoria-coral-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -s coral -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force

victoria-river-runs-red-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force

victoria-satellite-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -s satellite -z 15 -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force

victoria-dusk-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-dusk -s dusk -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force

victoria-night-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-night -s night -t config,map -b 50 -w 36 -h 24 -d 600 -f png --with-ocean --force
