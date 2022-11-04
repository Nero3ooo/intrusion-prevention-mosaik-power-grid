# Deployment

`Docker`-based distributed deployment of IDS components

# Installation instructions
For attack-engine first make sure docker can connect to display:

Linux:
```
xhost +"local:docker@" 
```
in ./config/environment change DISPLAY in ae.env
```
DISPLAY=$DISPLAY
```


Windows:
```
xming :0 -ac -clipboard -multiwindow

```
in ./config/environment change DISPLAY in ae.env
```
DISPLAY=hostip:0
```

MacOS:
```
brew install socat
brew cask install xquartz
open -a XQuartz
socat TCP-LISTEN:6000,reuseaddr,fork UNIX-CLIENT:\"$DISPLAY\"
```
in ./config/environment change DISPLAY in ae.env
```
DISPLAY=hostip:0
```

Main installation after display management:
```
docker network create --subnet 10.5.0.0/24 local_network_dev
docker-compose build
docker-compose up
```

### Port Mapping:
The docker-compose file exposes three ports for public use:

- Port 9000 - Visualization MOSAIK
- Port 8999 - Visualization IDS
- Port 8777 - Websocket for Requirement Violations

### Directory Structure
- **config**: config files
- **testbed**: MOSAIK Testbed
