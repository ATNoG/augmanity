FROM python:3.9

RUN useradd -m -d /home/bosch bosch
RUN ["apt-get", "update"]
ADD . /home/bosch/bridge
RUN ["pip","install","-r","/home/bosch/bridge/requirements.txt"]

ENTRYPOINT [ "python3" ]
CMD ["/home/bosch/bridge/bridge.py","--addr_ditto","10.0.13.32","--port_ditto","30525","--ditto_user","ditto","--ditto_pwd","ditto","--addr_influxdb","10.152.183.48","--port_influxdb","8086"]