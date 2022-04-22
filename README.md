# augmanity

## Kubernetes Installation
We are using microk8s due to its out-of-the-box kubernetes instances without having to go through the process of establishing a container runtime, networking... It is not, however, well suited for production environments.

### Installing snapd
```bash
$sudo apt update
$sudo apt install snapd
```
### Installing microk8s
```bash
$sudo snap install microk8s --classic
#wait for cluster to initiate
#validate cluster status
$sudo microk8s status --wait-ready
```

### Give microk8s permissions to atnoguser 
```bash
$sudo usermod -a -G microk8s atnoguser
$sudo chown -f -R atnoguser ~/.kube
#Reload user groups permissions
$newgrp microk8s
```

### Add required cloud2edge package modules
```bash
# Replace <interface> with the interface you want to use for your metallb instance
$LOCAL_ADDRESS=$(ip addr show <interface> | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)
$microk8s enable metrics-server
$microk8s enable storage
$microk8s enable dns
$microk8s enable $metallb:$LOCAL_ADDRESS-$LOCAL_ADDRESS
```

### Disable HA 
##### In development this shouldn't create a lot of problems. The decision behind this is that apparently microk8s HA has memory leaks
```bash
$microk8s disable ha-cluster --force
```

### Installing kubectl for ease of use
```bash
$sudo snap install kubectl --classic
# extract microk8s cluster config file so that kubectl can use it
$microk8s kubectl config view --raw > $HOME/.kube/config
```

### Installing helm
```bash
$curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
$chmod 700 get_helm.sh
$./get_helm.sh
```

### Add Eclipse Cloud2Edge packages repository to Helm
```bash
$helm repo add eclipse-iot https://eclipse.org/packages/charts
```

### Create k8s namespace
```bash
$NS=cloud2edge
$kubectl create namespace $NS
```
### Create a PV for services that are missing one
##### Detectable in the install via the --debug flag
##### Only if using a kubernetes installion that isn't microk8s
##### This is only an example, the proper yaml should follow the requirements of the PVC in the helm chart
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
        name: c2e-command-router-volume
spec:
  capacity: 
    storage: 100Mi
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: "/mnt/data"
```

### Apply the pv 
```bash
$kubectl apply -f <pv_file>
```


### Deploy c2e package using helm
```bash
$RELEASE=c2e
$helm install -n $NS --wait --timeout 30m $RELEASE eclipse-iot/cloud2edge --debug
```

### How to debug
```bash
$kubectl get pods -n cloud2edge
$kubectl describe pod <pod> -n cloud2edge
```

### Changing MQTT Config to accept data **>2KB**
##### This one is easier done after deployment since otherwise we need to first generate the template from helm chart or change the chart and recreate it
```bash
# Get all deployments
$kubectl get deployments -n cloud2edge
# Get the name of the mqtt-vertx-adapter
$kubectl edit deployment c2e-adapter-amqp-vertx -n cloud2edge 

```
```yaml
# Add the HONO_MQTT_MAXPAYLOADSIZE env variable (https://www.eclipse.org/hono/docs/admin-guide/mqtt-adapter-config/)
# .yaml that represents the mqtt-vertx deployment
 ...
 spec:
      containers:
      - name: "adapter-mqtt-vertx"
        image: "index.docker.io/eclipse/hono-adapter-mqtt-vertx-quarkus:1.12.1"
        ports:
        - name: health
          containerPort: 8088
          protocol: TCP
        - name: mqtt
          containerPort: 1883
          protocol: TCP
        - name: secure-mqtt
          containerPort: 8883
          protocol: TCP
        securityContext:
          privileged: false
        env:
        - name: JDK_JAVA_OPTIONS
          value: "-XX:MinRAMPercentage=80 -XX:MaxRAMPercentage=80"
        - name: KUBERNETES_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        - name: SMALLRYE_CONFIG_LOCATIONS
          value: "/opt/hono/config/logging-quarkus-dev.yml"
        - name: JAEGER_SERVICE_NAME
          value: "c2e-adapter-mqtt-vertx"
        - name: JAEGER_SAMPLER_TYPE
          value: "const"
        - name: JAEGER_SAMPLER_PARAM
          value: "0"
        - name: HONO_MQTT_MAXPAYLOADSIZE
          value: "10000"
...
```
### Adding influx to the cluster
```bash
# Add influx chart repo to helm
$helm repo add influxdata https://helm.influxdata.com/
$helm upgrade --install my-release influxdata/influxdb
```
### Adding grafana to the cluster
##### Using the grafana.yaml available in the repository
```bash
$kubectl create namespace grafana
$kubectl apply -f grafana.yaml
```

### Changing grafana config to accept query every 1 second
##### Add (based on the grafana documentation) the environment variable to the deployment
```yaml
containers:
  - name: grafana
    image: grafana/grafana:latest
    env:
      - name: GF_DASHBOARDS_MIN_REFRESH_INTERVAL
        value: "1s"
```

### Adding Influx DataSource to Grafana
- Enter grafana UI
- Click the Configuration Setting (gear icon)
- Click data sources
- Click add data source
- Select InfluxDb
- Specify the name of the influxdb datasource
- Specify the Query Language (InfluxQl or Flux)
### Adding bridge container image to Microk8s
```bash
# First copy the image to the host machine
$scp bridge.tar atnoguser@<ip>:~/bridge.tar
$microk8s ctr image import ~/bridge.tar
```
### Deploying the Bridge between Ditto SSE and Influx
##### Obtaining IP's and Ports for SSE and Influx
```bash
$kubetl get services -n cloud2edge
```
##### Changing the bridge.yaml accordingly
```yaml
# Changes the entrypoint and cmd of the container image to properly match the requirements of the application
# This can and should be changed to use k8s dns
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bridge
spec:
  selector:
    matchLabels:
      app: bridge
  replicas: 1
  template:
    metadata:
      labels:
        app: bridge
    spec:
      containers:
      - name: bridge
        image: bridge:latest
        imagePullPolicy: Never
        command: ["python3"]
        args: ["/home/bosch/bridge/bridge.py","--addr_ditto","<external_addr_ditto>","--port_ditto","<port_ditto>","--ditto_user","ditto","--ditto_pwd","ditto","--addr_influxdb","<cluster_internal_ip>","--port_influxdb","<influx_port>"]
```


### Obtaining all the ips and ports of cloud2edge
```bash
./setCloud2EdgeEnv.sh c2e cloud2edge
```

### If required set Ditto MongoDB to stop cleanup
```bash
curl -i -X POST -u ditto:ditto -H --data '{
  "targetActorSelection": "/user/thingsRoot/persistenceCleanup",
  "headers": {
    "aggregate": false,
    "is-grouped-topic": true
  },
  "piggybackCommand": {
    "type": "common.commands:modifyConfig",
    "config": {
     "enabled": false
    }
  }
}' http://${DITTO_API_IP}:${DITTO_API_PORT_HTTP}/devops/piggygack/things?timeout=10s
``` 

### Getting event stream of ditto receiving only thing,timestamp and features
#### Based on [DittoSSE](https://www.eclipse.org/ditto/httpapi-sse.html)
```bash
curl --http2 -u ditto:ditto -H 'Accept:text/event-stream' -N http://${DITTO_API_IP}:${DITTO_API_PORT_HTTP}/api/2/things?fields=thingId,attributes,_modified
```

### Add the backup_mongo to cron
```bash
$crontab -e atnoguser
# Add the kubectl to path to allow cron to run 
# or
# Use the full kubectl path (Prefered solution)
```
