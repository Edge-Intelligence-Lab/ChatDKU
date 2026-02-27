# Prometheus Monitoring Documentation

## What Is Prometheus?

Original documentation at: https://prometheus.io/docs/introduction/overview/

Prometheus is an open-source monitoring and alerting toolkit. Since its inception in 2012, many companies and organizations have adopted Prometheus,
and the project has a very active developer and user community. It is now a standalone open source project and maintained independently of any company.

Key features of Prometheus:
- **Multi-dimensional data model**: Time series data is identified by metric name and key/value pairs
- **Powerful query language**: PromQL allows flexible querying and aggregation of time series data
- **Efficient storage**: Time series storage is designed for high-performance metrics collection
- **Pull-based collection**: Prometheus scrapes metrics from instrumented targets
- **Service discovery**: Automatic discovery of targets for monitoring
- **Multiple integration modes**: Can be integrated with various exporters and libraries
- **Alerting**: Built-in alerting manager with configurable rules
- **Visualization**: Integration with Grafana and other visualization tools

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Applications  │───▶│   Metrics        │───▶│   Prometheus    │
│   (Services)    │    │   Exporters      │    │   Server        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │   Alertmanager  │
                                               │   (Routing)     │
                                               └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │   Notifications │
                                               │   (Email/Slack) │
                                               └─────────────────┘
```

## How to Use Prometheus

### Basic Concepts

1. **Metrics**: Numerical measurements collected over time
2. **Targets**: Services or applications that expose metrics
3. **Exporters**: Programs that expose existing metrics in Prometheus format
4. **Scraping**: The process of pulling metrics from targets
5. **PromQL**: Query language for retrieving and processing metrics

### Querying Metrics

Access the Prometheus web interface at `http://localhost:9090` to:
- Execute PromQL queries
- Browse available metrics
- Visualize time series data
- Check target status

#### Credentials
- Username: `admin`
- Password: `test`

How to change the password:
1. To create the password, run the following script at:

```python3 /datapool/prometheus/gen-pass.py```

2. Copy the hashed password and paste it into the `web.yml` file, so that it looks like this:
```yaml
basic_auth_users:
    admin: <HASHED_PASSWORD>
```
3. Restart the Prometheus container.

#### Example PromQL Queries:
```promql
# CPU usage by instance
rate(cpu_usage_total[5m]) by (instance)

# HTTP request rate
rate(http_requests_total[5m])

# High error rate alert
rate(http_requests_total{status=~"5.."}[5m]) > 0.1
```

## Monitored Services

| Service | Port | Metrics Endpoint |
|---------|------|------------------|
| tei-bge-m3 | 18080 | `/BAAI/bge-m3/metrics` |
| tei-bge-large | 18080 | `/BAAI/bge-large-en-v1.5/metrics` |
| sglang (LLM) | 18085 | `/BAAI/bge-large-en-v1.5/metrics` |
| Redis-exporter | 9121 | `/metrics` |

## Alerting

### Alert Rules

Our monitoring setup includes the following alert categories:

#### Infrastructure Alerts
- **Service Down**: Triggered when a service becomes unavailable. WIll ping everyone.
- **High Latency Alert**: **Haven't set this up yet.** 

## Getting Started

### Prerequisites

- Docker and Docker Compose (recommended)
- Sufficient disk space for metrics storage (recommended: 50GB+)

### Configuration Files

#### Main Configuration Location
- **Main config**: `/datapool/prometheus/prometheus.yml`
- **Prometheus auth config**: `/datapool/prometheus/web.yml`
- **Alert config**: `/datapool/prometheus/alertmanager.yml`
- **Rules config**: `/datapool/prometheus/rules/*.yml`

#### Key Configuration Files
```
/datapool/prometheus/
├── prometheus.yml             # Main Prometheus configuration
├── alertmanager.yml           # Alert routing configuration
├── gen-pass.py                # Script to generate hashed password
├── rules/                     # Alert rules directory
│   ├── targets_down.yml       # Infrastructure alerts
└── web.yml/                   # Prometheus basic auth config
```

### Starting Prometheus

> [!IMPORTANT]
> In the future, we should move Prometheus to a separate systemd service.

#### Docker Environment
```bash
# Start Prometheus container
sudo docker run -d \
  --name prometheus \
  -p 9090:9090 \
  --network=host \
  -v /datapool/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  -v /datapool/prometheus/rules:/etc/prometheus/rules \
  -v /datapool/prometheus/web.yml:/etc/prometheus/web.yml:ro \
  -v prometheus-data:/prometheus \
  prom/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.config.file=/etc/prometheus/web.yml

# Start Alertmanager container
sudo docker run -d \
  --name alertmanager \
  -p 9093:9093 \
  -v /datapool/prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro \
  -v alertmanager-data:/alertmanager \
  prom/alertmanager:latest \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --storage.path=/alertmanage
```
You might need to disown the process after starting it.

**We haven't set up Prometheus to run as a systemd service yet.**
**But this will be how you can run it in the future.**
#### Production Environment (Systemd)
```bash
# Start Prometheus service
sudo systemctl start prometheus

# Enable auto-start on boot
sudo systemctl enable prometheus

# Check status
sudo systemctl status prometheus

# View logs
sudo journalctl -u prometheus -f
```


### Verification Steps

1. **Check Prometheus UI**: Navigate to `http://localhost:9090`
2. **Verify Targets**: Go to Status → Targets to ensure all services are up
3. **Test Queries**: Execute simple queries to confirm data collection
4. **Validate Alerts**: Check Alertmanager for any active alerts

## Exporters

Read here to learn more about exporters: https://prometheus.io/docs/instrumenting/exporters/

Currently, we are using `Redis-exporter` to collect metrics from Redis.
Redis open source doesn't support the `/metrics` API endpoint, so we have to use the exporter.

To run `Redis-exporter`, you need to run the following command:

> [!IMPORTANT]
> In the future, we should use password files for extra security.

```bash
sudo docker run -d \                     
  --name redis_exporter \
  --network=host \                                     
  oliver006/redis_exporter \                                                
  --redis.addr=redis://127.0.0.1:6379 \                      
  --redis.user=default \            
  --redis.password=<password>
```
You might need to disown the process after starting it.

### Verification on exporter running correctly



## Maintenance and Operations

### Performance Tuning

#### Storage Optimization
- Configure retention period in `prometheus.yml`
- Set appropriate scrape intervals
- Monitor disk usage and plan capacity

#### Memory Optimization
- Adjust `--storage.tsdb.max-block-duration`
- Configure `--query.max-samples`
- Monitor memory usage patterns

### Troubleshooting

#### Common Issues

1. **Targets Not Scraping**
   - Check network connectivity
   - If you target is a docker container, sometimes you need to use `host.docker.internal`
   - Verify target endpoints are accessible
   - Review Prometheus logs for errors

2. **High Memory Usage**
   - Reduce scrape interval
   - Increase retention period settings
   - Check for metric cardinality issues

3. **Alert Not Firing**
   - Verify alert rule syntax
   - Check evaluation interval
   - Review Alertmanager configuration

#### Log Locations
- **Docker**: `sudo docker logs prometheus`

## Security Considerations

### Access Control
- Enabled basic authentication
- **Future Goal**: Use firewall rules to limit network access

### Data Protection
- **Future Goal**: Encrypt sensitive configuration files
- **Future Goal**: Use HTTPS for external communications
- **Future Goal**: Regularly rotate authentication credentials

## Integration with Other Tools

### **Future Goal** Grafana Integration
- Pre-built dashboards available
- Custom dashboard creation
- Alerting integration

---

- **Last Updated**: 2026-01-30
- **Version**: 1.0.0 
- **Maintainers**: Temuulen  
- **Contact**: te100@duke.edu
