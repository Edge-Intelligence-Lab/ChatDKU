#----CONFIG----
LOCUSTFILE="locustfile.py"
WORKERS=5
MASTER_HOST="${LOCUST_MASTER_HOST:-127.0.0.1}"
MASTER_LOG="master.log"
WORKER_LOG_PREFIX="worker"

# source <:venv>

mkdir -p locust_logs

echo "Starting Master ...."
nohup locust -f $LOCUSTFILE --master  --web-port 8089 > "locust_logs/${MASTER_LOG}" 2>&1 &

sleep 5
echo "Starting Worker"

for i in $(seq 1 $WORKERS); do
    echo "Starting worker $i..."
    nohup locust -f $LOCUSTFILE --worker --master-host=$MASTER_HOST > "locust_logs/${WORKER_LOG_PREFIX}${i}.log" 2>&1 &
done

echo "All done! Dashboard available at http://$MASTER_HOST:8089"
