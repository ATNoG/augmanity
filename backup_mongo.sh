/snap/bin/kubectl exec -it ditto-mongodb-7f9fb64588-j4kj6 -n cloud2edge -- rm -rf /tmp/*-things
/snap/bin/kubectl exec -it ditto-mongodb-7f9fb64588-j4kj6 -n cloud2edge -- mongodump --db=things --out=/tmp/$(date +"%FT%H%M")-things
/snap/bin/kubectl cp cloud2edge/ditto-mongodb-7f9fb64588-j4kj6:/tmp/ /tmp/
