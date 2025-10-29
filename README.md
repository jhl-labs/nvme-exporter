# NVMe Exporter

NVMe Exporter는 서버의 NVMe 디스크 상태 및 SMART 정보를 Prometheus 메트릭 형식으로 제공하는 Python 기반 Exporter입니다.

## 주요 기능

- NVMe 디스크의 SMART 정보(온도, 사용량, 오류 등) 실시간 수집 및 제공
- 여러 NVMe 디스크 동시 모니터링 지원
- Prometheus와 연동하여 손쉬운 시각화 가능

## 사용법

```bash
python server.py [디바이스명 ...] [옵션]
```

### 주요 옵션

- `디바이스명`  
  직접 모니터링할 NVMe 디바이스를 지정합니다. 예시: `nvme0n1 nvme1n1`
- `--device-all`  
  서버의 모든 NVMe 디바이스를 자동으로 탐색·모니터링합니다.
- `--port <포트번호>`  
  HTTP 서버가 사용할 포트 지정 (기본값: 9900)
- `--sudo`  
  nvme-cli를 실행할 때 sudo 권한을 사용합니다. (권한이 필요한 환경에서 사용)

### 예시

모든 NVMe 디바이스를 자동으로 모니터링하고, 9100 포트에서 실행:
```bash
python server.py --device-all --port 9100
```

특정 디바이스만 모니터링:
```bash
python server.py nvme0n1 nvme1n1 --port 9200
```

sudo 권한이 필요한 경우:
```bash
python server.py --device-all --sudo
```

## Prometheus 설정 예시

```yaml
scrape_configs:
  - job_name: 'nvme'
    static_configs:
      - targets: ['localhost:9900']
```

## 제공 메트릭 예시
```
# HELP nvme_metrics NVMe SMART data
# TYPE nvme_metrics gauge
nvme_critical_warning{device="nvme0n1"} 0
nvme_temperature{device="nvme0n1"} 47
nvme_available_spare{device="nvme0n1"} 100
nvme_available_spare_threshold{device="nvme0n1"} 10
nvme_percentage_used{device="nvme0n1"} 1
nvme_data_units_read{device="nvme0n1"} 4652335
nvme_data_units_written{device="nvme0n1"} 15463664
nvme_temperature_sensor_1{device="nvme0n1"} 41
nvme_temperature_sensor_2{device="nvme0n1"} 53
nvme_thermal_mgmt_t1_trans{device="nvme0n1"} 0
nvme_thermal_mgmt_t2_trans{device="nvme0n1"} 0
nvme_thermal_mgmt_t1_time{device="nvme0n1"} 0
nvme_thermal_mgmt_t2_time{device="nvme0n1"} 0
nvme_tbw_terabytes{device="nvme0n1"} 7.917
```

메트릭은 `/metrics` 엔드포인트에서 Prometheus 포맷으로 제공됩니다.

## 라이선스

이 프로젝트는 GNU Affero General Public License v3.0(AGPL)로 배포됩니다.

