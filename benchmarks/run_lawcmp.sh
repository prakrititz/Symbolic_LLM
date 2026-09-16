#!/usr/bin/env bash
# Core-laws vs extended-laws comparison.
#
# Runs one (model, law-set) arm at a time and unloads the model from Ollama
# between arms: holding llama3.1 (~5.8 GB) and qwen3.5 (~7 GB) resident at the
# same time exhausts memory on this machine and the run gets killed.
set -u

OUT=benchmarks/results/results_lawcmp.jsonl
LOG=benchmarks/results/run_lawcmp.log
: > "$LOG"

unload() {
  curl -s http://localhost:11434/api/generate \
    -d "{\"model\":\"$1\",\"keep_alive\":0}" >/dev/null 2>&1
  sleep 3
}

for arm in core extended; do
  for cfg in llama3.1 qwen3.5-nothink; do
    case "$cfg" in
      llama3.1)        model=llama3.1:latest ;;
      qwen3.5-nothink) model=qwen3.5:latest ;;
    esac
    echo "### arm=$arm config=$cfg" | tee -a "$LOG"
    PYTHONPATH="$PWD" python benchmarks/run_bench.py \
      --configs "$cfg" --repeats 2 --max-retries 4 --budget 30 \
      --max-depth 6 --temperature 0.2 --laws "$arm" --out "$OUT" 2>&1 | tee -a "$LOG"
    unload "$model"
  done
done

echo "ALL ARMS COMPLETE" | tee -a "$LOG"
