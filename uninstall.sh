#!/bin/bash

echo "Removing jfc link..."
if rm "$HOME/bin/jfc"; then
    echo -e "\033[32mDone.\033[0m"
else
    echo "Something went wrong."
fi
