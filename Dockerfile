FROM ubuntu:jammy

RUN apt update && \
    apt install -y \
        python3-pip 

WORKDIR /toybox

COPY requirements.txt .

# install deps
RUN pip install -r requirements.txt

# pull this repo into the container...
COPY . .

RUN cd toybox_msgs && ./build_messages

# ... and install the python packages
RUN pip install -e \
    ./toybox_core \
    ./toybox_msgs

# build the messages

# TODO: add our packages to the path explicitly, 
# until I figure out why that doesn't work automatically when I pip install
# ENV PYTHONPATH=/toybox
