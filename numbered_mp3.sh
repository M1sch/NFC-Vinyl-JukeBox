#!/bin/bash
n=1
for f in *.mp3; do
  num=$(printf "%03d" "$n")
  mv -- "$f" "${num}.mp3"
  n=$((n+1))
done
