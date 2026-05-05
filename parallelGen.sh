run_task() {
    game_file="$1"
    game_name=$(basename "$game_file" .py)
    xvfb-run -a -s "-screen 0 854x480x24" python generateAutoplayDataset.py \
        --game-class games."$game_name" \
        --output-root debug \
        --max-seconds 600 \
        --count 5 \
        --random-variant
}
export -f run_task

# Generate the list of files repeated 100 times
files=(games/*.py)
for i in {1..100}; do
    printf "%s\n" "${files[@]}"
done | parallel -j 10 run_task {}