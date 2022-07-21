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

5. Configure the gitea system webhook for the incremental perception service. See the figure below.

<details>
  <summary>Click to present.</summary>

  You need to change the IP address and the administrator account by yourself.

  ![image](pics/gitea-system-webhook-setting.png)
</details>

6. Download [TXL](http://www.txl.ca/download/16963-txl10.8b.linux64.tar.gz) using command `wget http://www.txl.ca/download/16963-txl10.8b.linux64.tar.gz`.

7. Download TXL:
```
tar -zxvf 16963-txl10.8b.linux64.tar.gz
rm 16963-txl10.8b.linux64.tar.gz
mv txl10.8b.linux64 services/parser/txl
mkdir services/parser/txl/grammers
mkdir services/parser/txl/grammers/java
```

8. Append Java Grammer:
```
wget http://www.txl.ca/examples/Grammars/Java8/Java8.tar.gz
tar -zxvf Java8.tar.gz
rm Java8.tar.gz
mv Java8/java.* services/parser/txl/grammers/java
rm -fr Java8
wget http://www.txl.ca/examples/Grammars/BOM/BOM.tar.gz
tar -zxvf BOM.tar.gz
rm BOM.tar.gz
mv BOM/bom.grm services/parser/txl/grammers/java
rm -fr BOM
wget https://www.txl.ca/download/20818-NiCad-6.2.tar.gz
tar -zxvf 20818-NiCad-6.2.tar.gz
rm 20818-NiCad-6.2.tar.gz
cp NiCad-6.2/txl/java-extract-functions.txl services/parser/txl/grammers/java
cp NiCad-6.2/txl/nicad.grm services/parser/txl/grammers/java
rm -fr NiCad-6.2
```
