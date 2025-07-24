all: edmonton-coral edmonton-river-runs-red edmonton-dusk edmonton-night victoria-coral victoria-river-runs-red victoria-dusk victoria-night

start-at-config: edmonton-coral-config edmonton-river-runs-red-config edmonton-satellite-config edmonton-dusk-config edmonton-night-config victoria-coral-config victoria-river-runs-red-config victoria-satellite-config victoria-dusk-config victoria-night-config

edmonton-coral:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -s coral -b 30 -w 36 -h 24 -z 5 -d 600 -f png

edmonton-river-runs-red:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red -b 30 -w 36 -h 24 -z 5 -d 600 -f png

edmonton-satellite:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -b 30 -w 36 -h 24 -z 14 -d 600 -f png

edmonton-dusk:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-dusk -s dusk -b 30 -w 36 -h 24 -z 5 -d 600 -f png

edmonton-night:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-night -s night -b 30 -w 36 -h 24 -z 5 -d 600 -f png

victoria-coral:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -s coral -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean

victoria-river-runs-red:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean

victoria-satellite:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -s satellite -b 100 -w 24 -h 36 -z 8 -d 600 -f png --with-ocean

victoria-dusk:
    ./map-pipeline.sh "Victoria, BC" output/victoria-dusk -s dusk -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean

victoria-night:
    ./map-pipeline.sh "Victoria, BC" output/victoria-night -s night -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean

edmonton-coral-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -s coral -t config,map -b 30 -w 36 -h 24 -z 5 -d 600 -f png --force

edmonton-river-runs-red-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red -t config,map -b 30 -w 36 -h 24 -z 5 -d 600 -f png --force

edmonton-satellite-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -t config,map -b 30 -w 36 -h 24 -z 14 -d 600 -f png --force

edmonton-dusk-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-dusk -s dusk -t config,map -b 30 -w 36 -h 24 -z 5 -d 600 -f png --force

edmonton-night-config:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-night -s night -t config,map -b 30 -w 36 -h 24 -z 5 -d 600 -f png --force

victoria-coral-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -s coral -t config,map -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean --force

victoria-river-runs-red-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red -t config,map -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean --force

victoria-satellite-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -s satellite -t config,map -b 100 -w 24 -h 36 -z 8 -d 600 -f png --with-ocean --force

victoria-dusk-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-dusk -s dusk -t config,map -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean --force

victoria-night-config:
    ./map-pipeline.sh "Victoria, BC" output/victoria-night -s night -t config,map -b 100 -w 24 -h 36 -z 5 -d 600 -f png --with-ocean --force
