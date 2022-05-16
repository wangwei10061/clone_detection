FROM python:3.7.11

# RUN pip install --upgrade pip

RUN useradd -ms /bin/bash myuser
USER myuser
WORKDIR /home/myuser

ENV PATH="/home/myuser/.local/bin:${PATH}"

COPY --chown=myuser:myuser . .
RUN pip install --user -r requirements.txt > /dev/null 2>&1
CMD [ "python", "./services/CodeStartPerception.py"]
