#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset
# set -o xtrace

SCRIPT_DIR="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit ; pwd -P)"
TOYBOX_DIR="${1:-"${SCRIPT_DIR}"}"

pushd "${TOYBOX_DIR}" >/dev/null 2>&1 || exit

# install any pip dependencies
pip install -r requirements.txt

# Build the messages here first
# TODO: just build the messages as part of the pip install phase???
(
    cd ./toybox_msgs || exit
    ./build_messages
    cd ..
)

echo "--- Installing toybox_* packages with pip ---"
if ! pip install -e ./toybox_*; then
    echo "Failed to install toybox packages"
    exit 1
fi
echo "--- Finished installing toybox_* packages ---"

popd >/dev/null 2>&1 || exit # $TOYBOX_DIR

if ! grep -q "# toybox: " "${HOME}/.bashrc"; then
    echo "--- Adding toybox setup to .bashrc ---"
    {
        echo ""; \
        echo "# toybox: "; \
        echo "export PATH=\"$(python3 -m site --user-base)/bin:\${PATH}\"";
    } >> "${HOME}/.bashrc"
    # shellcheck disable=SC1091
    source "${HOME}/.bashrc"
    echo "--- Finished adding toybox setup to .bashrc ---"
fi
