FROM python:3.11-bookworm

ADD requirements.txt /
RUN pip3 install -r /requirements.txt

ADD main.py playback.py /bin/
RUN chmod +x /bin/main.py

CMD /bin/main.py
