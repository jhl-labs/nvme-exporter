#!/usr/bin/env python3
import subprocess, re, sys, argparse, socketserver, glob
from http.server import BaseHTTPRequestHandler, HTTPServer

# ------------------ 정규식 패턴 ------------------
PATTERNS_ALL = {
    "critical_warning": r"critical_warning\s*:\s*(\d+)",
    "temperature": r"temperature\s*:\s*(\d+)\s*[°º]?\s*([CFK])?",
    "available_spare": r"available_spare\s*:\s*(\d+)%",
    "available_spare_threshold": r"available_spare_threshold\s*:\s*(\d+)%",
    "percentage_used": r"percentage_used\s*:\s*(\d+)%",
    "data_units_read": r"data\s*units\s*read\s*:\s*([\d,]+)",
    "data_units_written": r"data\s*units\s*written\s*:\s*([\d,]+)",
    "host_read_commands": r"host\s*read\s*commands\s*:\s*([\d,]+)",
    "host_write_commands": r"host\s*write\s*commands\s*:\s*([\d,]+)",
    "controller_busy_time": r"controller\s*busy\s*time\s*:\s*([\d,]+)",
    "power_cycles": r"power\s*cycles\s*:\s*(\d+)",
    "power_on_hours": r"power\s*on\s*hours\s*:\s*(\d+)",
    "unsafe_shutdowns": r"unsafe\s*shutdowns\s*:\s*(\d+)",
    "media_errors": r"media\s*errors\s*:\s*(\d+)",
    "num_err_log_entries": r"num\s*err\s*log\s*entries\s*:\s*(\d+)",
    "temperature_sensor_1": r"temperature\s*sensor\s*1\s*:\s*(\d+)\s*[°º]?\s*([CFK])?",
    "temperature_sensor_2": r"temperature\s*sensor\s*2\s*:\s*(\d+)\s*[°º]?\s*([CFK])?",
    "thermal_mgmt_t1_trans": r"thermal\s*management\s*T1\s*Trans\s*Count\s*:\s*(\d+)",
    "thermal_mgmt_t2_trans": r"thermal\s*management\s*T2\s*Trans\s*Count\s*:\s*(\d+)",
    "thermal_mgmt_t1_time": r"thermal\s*management\s*T1\s*Total\s*Time\s*:\s*(\d+)",
    "thermal_mgmt_t2_time": r"thermal\s*management\s*T2\s*Total\s*Time\s*:\s*(\d+)",
}

def f_to_c(f): return round((f - 32) * 5/9, 1)

# ------------------ SMART 파서 ------------------
def get_nvme_metrics(device, sudo=False):
    cmd = ["nvme", "smart-log", f"/dev/{device}"]
    if sudo:
        cmd.insert(0, "sudo")

    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return {}

    data = {}
    for key, pattern in PATTERNS_ALL.items():
        m = re.search(pattern, output, re.IGNORECASE)
        if not m:
            continue
        val = int(m.group(1).replace(",", ""))
        # 온도 단위 보정 (°F, °K)
        if key.startswith("temperature") and m.lastindex and m.group(2):
            unit = m.group(2).upper()
            if unit == "F":
                val = int(f_to_c(val))
            elif unit == "K":
                val = int(val - 273.15)
        data[key] = val

    # TBW 계산 (512,000 bytes per data unit)
    if "data_units_written" in data:
        data["tbw_terabytes"] = round(data["data_units_written"] * 512_000 / 1e12, 3)
    return data

# ------------------ Prometheus 포맷 ------------------
def format_prometheus_metrics(metrics, device):
    lines = ["# HELP nvme_metrics NVMe SMART data", "# TYPE nvme_metrics gauge"]
    for k, v in metrics.items():
        lines.append(f"nvme_{k}{{device=\"{device}\"}} {v}")
    return "\n".join(lines) + "\n"

# ------------------ HTTP 핸들러 ------------------
class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        metrics_output = ""
        for dev in self.server.devices:
            data = get_nvme_metrics(dev, sudo=self.server.use_sudo)
            if data:
                metrics_output += format_prometheus_metrics(data, dev)

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(metrics_output.encode("utf-8"))

    def log_message(self, *args):
        return  # 로그 억제

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

# ------------------ 메인 ------------------
def main():
    parser = argparse.ArgumentParser(description="NVMe SMART Prometheus exporter (no prometheus_client)")
    parser.add_argument("devices", nargs="*", help="NVMe device(s), e.g. nvme0n1 nvme1n1")
    parser.add_argument("--device-all", action="store_true", help="Monitor all NVMe devices automatically")
    parser.add_argument("--port", type=int, default=9900, help="HTTP port (default: 9900)")
    parser.add_argument("--sudo", action="store_true", help="Use sudo for nvme-cli")
    args = parser.parse_args()

    # --device-all 옵션 처리
    if args.device_all:
        found = sorted([p.split("/")[-1] for p in glob.glob("/dev/nvme*n1")])
        if not found:
            print("[ERROR] No NVMe devices found under /dev/nvme*n1")
            sys.exit(1)
        devices = found
        print(f"[INFO] Auto-discovered NVMe devices: {devices}")
    elif args.devices:
        devices = args.devices
    else:
        print("[ERROR] You must specify devices or use --device-all")
        sys.exit(1)

    print(f"[INFO] Serving NVMe metrics for {[f'/dev/{d}' for d in devices]} on port {args.port}")

    # 최초 1회 SMART 결과 콘솔 출력
    for dev in devices:
        metrics = get_nvme_metrics(dev, sudo=args.sudo)
        if not metrics:
            print(f"[WARN] Failed to get SMART data for {dev}")
            continue
        print(f"\n=== Initial SMART Data for /dev/{dev} ===")
        for k, v in metrics.items():
            print(f"{k:25s}: {v}")

    print("\n[INFO] Exporter is now serving /metrics endpoint...\n")

    server = ThreadedHTTPServer(("", args.port), MetricsHandler)
    server.devices = devices
    server.use_sudo = args.sudo
    server.serve_forever()

if __name__ == "__main__":
    main()
