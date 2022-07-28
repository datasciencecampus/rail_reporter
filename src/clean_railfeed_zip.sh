#!/bin/bash

# Cleans weird feed artefacts/errors in format

# Retrieve filename and directory from arguments
# TODO: Have single filepath argument, then expand
while getopts f:d: flag
do
    case "${flag}" in
        f) FILENAME=${OPTARG};;
        d) WORKDIR=${OPTARG};;
    esac
done

# Move to directory containing file to be fixed
cd "$WORKDIR"

unzip "$FILENAME".zip -d "$FILENAME"

# open the unziped folder
cd "$FILENAME"

# move files to the top dir if needed (449)
mv "$FILENAME"/*.*  .

# convert ext to lower case if needed (448)
rename 's/\.([^.]+)$/l.\L$1/' *

# remove comment lines from all files (needed in both 448&449)
mkdir new"$FILENAME" 

for file in *.*; do sed '/^\/!!/ d' <"$file" >new"$FILENAME"/"$file"; done

# zip, jump back up one level and clean up
zip -r ../new"$FILENAME".zip new"$FILENAME"
cd ..
rm -r "$FILENAME"