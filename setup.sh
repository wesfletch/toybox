#!/usr/bin/env bash

SCRIPT_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit ; pwd -P )"

TOYBOX_DIR="${1:-"${SCRIPT_DIR}"}"

pushd "${TOYBOX_DIR}" >/dev/null 2>&1 || exit

# install any pip dependencies
pip install -r requirements.txt

(
    cd ./toybox_msgs || exit
    ./build_messages
    cd ..
)

echo "--- Installing toybox_* packages with pip ---"
for package_dir in toybox_*/; do
    echo "--- Attempting to install ${package_dir} ---"
    if ! pip install -e "${package_dir}"; then
        echo "Failed to install ${package_dir}"
    fi
    echo "------------------------------------------"
done
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

exit 0