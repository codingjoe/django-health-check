# Monitoring Integration

This guide covers how to integrate django-health-check with monitoring and observability platforms like Prometheus and Grafana.

## Prometheus Integration

Django-health-check supports exporting metrics in Prometheus exposition format, making it easy to scrape health check data with Prometheus.

### Accessing Prometheus Metrics

You can access health check metrics in Prometheus format in two ways:

#### 1. Using the `format` query parameter

```bash
curl http://localhost:8000/health/?format=prometheus
```

#### 2. Using the `Accept` HTTP header

```bash
curl -H "Accept: application/openmetrics-text" http://localhost:8000/health/
```

Or:

```bash
curl -H "Accept: text/plain" http://localhost:8000/health/
```

### Metrics Exposed

The Prometheus endpoint exposes the following metrics:

#### `django_health_check_status`

A gauge metric indicating the health status of each individual check:
- `1` = healthy
- `0` = unhealthy

Each metric includes a `check` label with the name of the health check.

**Example:**
```
# HELP django_health_check_status Health check status (1 = healthy, 0 = unhealthy)
# TYPE django_health_check_status gauge
django_health_check_status{check="DatabaseBackend"} 1
django_health_check_status{check="CacheBackend"} 1
django_health_check_status{check="StorageHealthCheck"} 0
```

#### `django_health_check_response_time_seconds`

A gauge metric showing the response time of each health check in seconds.

**Example:**
```
# HELP django_health_check_response_time_seconds Health check response time in seconds
# TYPE django_health_check_response_time_seconds gauge
django_health_check_response_time_seconds{check="DatabaseBackend"} 0.001234
django_health_check_response_time_seconds{check="CacheBackend"} 0.000567
django_health_check_response_time_seconds{check="StorageHealthCheck"} 0.089012
```

#### `django_health_check_overall_status`

A gauge metric indicating the overall health status:
- `1` = all checks are healthy
- `0` = at least one check is unhealthy

**Example:**
```
# HELP django_health_check_overall_status Overall health check status (1 = all healthy, 0 = at least one unhealthy)
# TYPE django_health_check_overall_status gauge
django_health_check_overall_status 0
```

### Configuring Prometheus to Scrape Metrics

Add the following to your Prometheus configuration (`prometheus.yml`):

```yaml
scrape_configs:
  - job_name: 'django-health-check'
    scrape_interval: 30s
    scrape_timeout: 10s
    metrics_path: '/health/'
    params:
      format: ['prometheus']
    static_configs:
      - targets: ['your-django-app:8000']
        labels:
          app: 'my-django-app'
          environment: 'production'
```

### Authentication

If your health check endpoint requires authentication, you can configure Prometheus to use basic authentication:

```yaml
scrape_configs:
  - job_name: 'django-health-check'
    scrape_interval: 30s
    metrics_path: '/health/'
    params:
      format: ['prometheus']
    basic_auth:
      username: 'prometheus'
      password: 'your-secret-password'
    static_configs:
      - targets: ['your-django-app:8000']
```

Alternatively, you can use bearer token authentication:

```yaml
scrape_configs:
  - job_name: 'django-health-check'
    scrape_interval: 30s
    metrics_path: '/health/'
    params:
      format: ['prometheus']
    bearer_token: 'your-bearer-token'
    static_configs:
      - targets: ['your-django-app:8000']
```

## Grafana Integration

Once Prometheus is scraping your health check metrics, you can create dashboards in Grafana to visualize the data.

### Setting Up a Data Source

1. In Grafana, go to **Configuration** > **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Enter your Prometheus server URL (e.g., `http://prometheus:9090`)
5. Click **Save & Test**

### Creating a Dashboard

Here's an example Grafana dashboard configuration with useful panels:

#### Panel 1: Overall Health Status

**Query:**
```promql
django_health_check_overall_status
```

**Visualization:** Stat panel
- Set thresholds: 
  - Red: 0 to 0.5 (unhealthy)
  - Green: 0.5 to 1 (healthy)

#### Panel 2: Individual Check Status

**Query:**
```promql
django_health_check_status
```

**Visualization:** Time series or bar gauge
- Group by the `check` label
- Set thresholds:
  - Red: 0 to 0.5 (unhealthy)
  - Green: 0.5 to 1 (healthy)

#### Panel 3: Check Response Times

**Query:**
```promql
django_health_check_response_time_seconds
```

**Visualization:** Time series
- Group by the `check` label
- Unit: seconds (s)

#### Panel 4: Slowest Checks

**Query:**
```promql
topk(5, django_health_check_response_time_seconds)
```

**Visualization:** Bar gauge
- Shows the 5 slowest health checks

#### Panel 5: Failed Checks Count

**Query:**
```promql
count(django_health_check_status == 0)
```

**Visualization:** Stat panel
- Shows the number of currently failing checks

### Example Dashboard JSON

Here's a complete Grafana dashboard JSON you can import:

```json
{
  "dashboard": {
    "title": "Django Health Check",
    "panels": [
      {
        "title": "Overall Health Status",
        "type": "stat",
        "targets": [
          {
            "expr": "django_health_check_overall_status"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "value": 0, "color": "red" },
                { "value": 0.5, "color": "green" }
              ]
            },
            "mappings": [
              { "value": 0, "text": "Unhealthy" },
              { "value": 1, "text": "Healthy" }
            ]
          }
        }
      },
      {
        "title": "Check Status",
        "type": "bargauge",
        "targets": [
          {
            "expr": "django_health_check_status",
            "legendFormat": "{{check}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "value": 0, "color": "red" },
                { "value": 0.5, "color": "green" }
              ]
            }
          }
        }
      },
      {
        "title": "Response Times",
        "type": "timeseries",
        "targets": [
          {
            "expr": "django_health_check_response_time_seconds",
            "legendFormat": "{{check}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "s"
          }
        }
      }
    ]
  }
}
```

### Setting Up Alerts

You can create alerts in Grafana to notify you when health checks fail:

1. Create a new alert rule
2. Set the query to: `django_health_check_overall_status < 1`
3. Configure the alert condition (e.g., trigger if value is below 1 for 1 minute)
4. Set up notification channels (email, Slack, PagerDuty, etc.)

Example alert rule:

```yaml
- alert: DjangoHealthCheckFailed
  expr: django_health_check_overall_status < 1
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Django application health check failed"
    description: "At least one health check is failing for {{ $labels.app }}"
```

## Other Monitoring Tools

While this guide focuses on Prometheus and Grafana, django-health-check also supports other formats:

- **JSON**: For custom monitoring solutions (use `?format=json` or `Accept: application/json`)
- **RSS/Atom**: For feed readers (use `?format=rss`, `?format=atom`, or appropriate Accept headers)
- **HTML**: For human-readable status pages (default format)

These formats can be integrated with various monitoring tools like Datadog, New Relic, or custom monitoring scripts.

## Best Practices

1. **Scrape Interval**: Set an appropriate scrape interval (30-60 seconds) to balance freshness with system load
2. **Timeout**: Configure timeouts to handle slow health checks gracefully
3. **Labels**: Use labels in Prometheus to distinguish between different environments and applications
4. **Alerting**: Set up alerts for critical health checks to be notified immediately
5. **Dashboards**: Create dashboards that show both current status and historical trends
6. **Performance**: Monitor the response times of health checks to identify performance issues
