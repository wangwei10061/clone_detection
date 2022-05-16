# LSICCDS_server
LSICCDS (large-scale incremental code clone detection system)

This is the server part of LSICCDS system

## How to use this
As all the parts are based on docker. So install docker on your server first. Here is a [guide](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04) for ubuntu 20.04.
Then install docker-compose by running `sudo apt install docker-compose`.

Add priviledge for the user.
```
sudo groupadd docker
sudo gpasswd -a $USER docker
newgrp docker
docker ps # test whether docker command can be used
```

1. `docker network create LSICCDS_server` to create the network.
2. `cd dependencies`
3. `docker-compose up -d` to install all the dependent services, including gitea (the dependent mysql), rabbitmq, elasticsearch, kibana.
  - Error may occur when installing elasticsearch and kibana, you need to:
    - `sudo chmod 777 -R dependencies/elasticsearch`
    - `sudo chmod 777 -R dependencies/kibana`
    - `docker-compose up -d`
4. Configure the gitea settings for initialization. See the figure below.
<details>
  <summary>Click to present.</summary>

  You need to change the IP address and the administrator account by yourself.

  ![image](pics/gitea-setting.jpeg)
</details>
