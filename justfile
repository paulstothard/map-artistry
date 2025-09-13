# Common variables
EDMONTON_W := "24"
EDMONTON_H := "24"
EDMONTON_B := "5"
EDMONTON_DPI := "600"
EDMONTON_FMT := "pdf"

EDMONTON_Z := "5"
EDMONTON_Z_SAT := "17"

VICTORIA_W := "24"
VICTORIA_H := "24"
VICTORIA_B := "55"
VICTORIA_DPI := "600"
VICTORIA_FMT := "pdf"

VICTORIA_Z := "5"
VICTORIA_Z_SAT := "16"

all: edmonton-coral copy-edmonton-shared edmonton-river-runs-red edmonton-blue-yellow victoria-coral copy-victoria-shared victoria-river-runs-red edmonton-satellite victoria-satellite

edmonton-coral:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-coral -s coral -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

copy-edmonton-shared:
    mkdir -p output/edmonton-river-runs-red output/edmonton-blue-yellow output/edmonton-satellite
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-river-runs-red/ output/edmonton-blue-yellow/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='satellite.tif' --exclude='.DS_Store' output/edmonton-coral/ output/edmonton-satellite/

edmonton-river-runs-red:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-river-runs-red -s river_runs_red -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

edmonton-blue-yellow:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-blue-yellow -s blue-yellow -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

edmonton-satellite:
    ./map-pipeline.sh "Edmonton, Alberta" output/edmonton-satellite -s satellite -b {{EDMONTON_B}} -w {{EDMONTON_W}} -h {{EDMONTON_H}} -z {{EDMONTON_Z_SAT}} -d {{EDMONTON_DPI}} -f {{EDMONTON_FMT}}

victoria-coral:
    ./map-pipeline.sh "Victoria, BC" output/victoria-coral -s coral -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

copy-victoria-shared:
    mkdir -p output/victoria-river-runs-red output/victoria-satellite
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='.DS_Store' output/victoria-coral/ output/victoria-river-runs-red/
    rsync -av --exclude='config.yaml' --exclude='map.*' --exclude='satellite.tif' --exclude='.DS_Store' output/victoria-coral/ output/victoria-satellite/

victoria-river-runs-red:
    ./map-pipeline.sh "Victoria, BC" output/victoria-river-runs-red -s river_runs_red -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

victoria-satellite:
    ./map-pipeline.sh "Victoria, BC" output/victoria-satellite -s satellite -b {{VICTORIA_B}} -w {{VICTORIA_W}} -h {{VICTORIA_H}} -z {{VICTORIA_Z_SAT}} -d {{VICTORIA_DPI}} -f {{VICTORIA_FMT}} --with-ocean

publish:
    mkdir -p publish
    find output -name "map.*" -type f | while read -r mapfile; do \
        folder=$(basename $(dirname "$mapfile")); \
        extension="${mapfile##*.}"; \
        cp "$mapfile" "publish/${folder}.${extension}"; \
    done
    @echo "Published maps to publish/ folder"

clean:
    rm -rf output

clean-maps:
    find output -type f \( -name "map.*" \) -delete

clean-maps-and-configs:
    find output -type f \( -name "map.*" -o -name "config.yaml" \) -delete