FROM debian

RUN apt update
RUN apt upgrade -y
RUN apt install -y python3 python3-pip

ADD requirements.txt /
RUN pip3 install -r /requirements.txt

ADD main.py /bin
RUN chmod +x /bin/main.py

CMD /bin/main.py
