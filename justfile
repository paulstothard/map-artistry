# Common variables
EDMONTON_W := "36"
EDMONTON_H := "24"
EDMONTON_B := "30"
EDMONTON_DPI := "600"
EDMONTON_FMT := "png"

EDMONTON_Z := "5"
EDMONTON_Z_SAT := "14"

VICTORIA_W := "24"
VICTORIA_H := "36"
VICTORIA_B := "200"
VICTORIA_DPI := "600"
VICTORIA_FMT := "png"

VICTORIA_Z := "5"
VICTORIA_Z_SAT := "8"

all: edmonton-coral copy-edmonton-shared edmonton-river-runs-red edmonton-dusk edmonton-night victoria-coral copy-victoria-shared victoria-river-runs-red victoria-dusk victoria-night

edmonton-coral:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -s coral -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

copy-edmonton-shared:
    mkdir -p output/edmonton-river-runs-red output/edmonton-dusk output/edmonton-night output/edmonton-satellite
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-river-runs-red/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-dusk/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-night/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='satellite.tif' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-satellite/

edmonton-river-runs-red:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

edmonton-dusk:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-dusk -s dusk -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

edmonton-night:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-night -s night -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

edmonton-satellite:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z_SAT}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

victoria-coral:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -s coral -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

copy-victoria-shared:
    mkdir -p output/victoria-river-runs-red output/victoria-dusk output/victoria-night output/victoria-satellite
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/victoria-coral/ output/victoria-river-runs-red/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/victoria-coral/ output/victoria-dusk/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/victoria-coral/ output/victoria-night/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='satellite.tif' --exclude='.DS_Store' output/victoria-coral/ output/victoria-satellite/

victoria-river-runs-red:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

victoria-dusk:
    ./map-pipeline.sh "Victoria, BC" output/victoria-dusk -s dusk -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

victoria-night:
    ./map-pipeline.sh "Victoria, BC" output/victoria-night -s night -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

victoria-satellite:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -s satellite -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z_SAT}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean