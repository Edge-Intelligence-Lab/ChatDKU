#!/bin/bash
# Count the number and total size of the files grouped by the extension in RAG_data
# Adapted from: https://askubuntu.com/questions/454564/count-total-number-of-files-in-particular-directory-with-specific-extension

cd "$1"

find . -type f \
	| egrep -o "\.[a-zA-Z0-9]+$" \
	| sort -u \
	| LC_ALL=C xargs -I '%' find . -type f -name '*%' -exec du -ch {} + -exec bash -c 'echo %' \; \
    | egrep "^\.[a-zA-Z0-9]+$|total$" \
    | uniq -c \
    | paste - - \
    | awk '{print sprintf("%-10s", $2), sprintf("%-10s", $1), $4}'

du -sh . | awk '{print "Total:", $1}'
