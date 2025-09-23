#!/usr/bin/env python3
"""
load_test.py — Async load tester (an toàn, yêu cầu --confirm trước khi chạy).

Cách dùng:
    python load_test.py --url https://example.com --requests 200 --concurrency 20 --confirm

Tính năng:
 - Gửi nhiều request song song bằng asyncio + aiohttp.
 - Đo tổng số request, % thành công, lỗi, thời gian phản hồi trung bình / p95.
 - Có chế độ dry-run (mặc định không gửi request, trừ khi có --confirm).
 - Hỗ trợ GET/POST/PUT/DELETE, custom headers, POST body, tắt SSL verify.
"""

import argparse
import asyncio
import time
from statistics import mean, median

try:
    import aiohttp
except ImportError:
    print("Thiếu aiohttp. Cài bằng: pip install aiohttp")
    raise SystemExit(1)


async def worker(name, session, url, method, payload, headers, count, results, semaphore, timeout):
    """Mỗi worker gửi count request."""
    for i in range(count):
        async with semaphore:
            start = time.perf_counter()
            try:
                async with session.request(method, url, data=payload, headers=headers, timeout=timeout) as resp:
                    status = resp.status
                    await resp.read()  # đọc toàn bộ response
                elapsed = (time.perf_counter() - start) * 1000
                results.append((status, elapsed, None))
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                results.append((None, elapsed, str(e)))


async def run_test(args):
    total_requests = args.requests
    concurrency = args.concurrency
    per_worker = total_requests // concurrency
    remainder = total_requests % concurrency

    connector = aiohttp.TCPConnector(ssl=not args.insecure)
    timeout = aiohttp.ClientTimeout(total=args.request_timeout)

    headers = {}
    if args.headers:
        for h in args.headers.split(";"):
            if ":" in h:
                k, v = h.split(":", 1)
                headers[k.strip()] = v.strip()

    payload = args.data.encode() if args.data else None
    results = []
    semaphore = asyncio.Semaphore(args.max_inflight)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for i in range(concurrency):
            count = per_worker + (1 if i < remainder else 0)
            if count > 0:
                if args.ramp_up and i > 0:
                    await asyncio.sleep(args.ramp_up)
                tasks.append(asyncio.create_task(worker(i, session, args.url, args.method,
                                                       payload, headers, count, results,
                                                       semaphore, timeout)))
        start_all = time.perf_counter()
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_all

    # Thống kê kết quả
    statuses = [r[0] for r in results if r[0] is not None]
    errors = [r for r in results if r[0] is None]
    latencies = [r[1] for r in results]

    def pct(n): return (n / len(results) * 100) if results else 0
    succ = sum(1 for s in statuses if 200 <= s < 300)
    redirect = sum(1 for s in statuses if 300 <= s < 400)
    client_err = sum(1 for s in statuses if 400 <= s < 500)
    server_err = sum(1 for s in statuses if 500 <= s < 600)

    print("=" * 60)
    print(f"Target URL        : {args.url}")
    print(f"Total Requests    : {len(results)}")
    print(f"Success (2xx)     : {succ} ({pct(succ):.2f}%)")
    print(f"Redirect (3xx)    : {redirect}")
    print(f"Client Error (4xx): {client_err}")
    print(f"Server Error (5xx): {server_err}")
    print(f"Exceptions        : {len(errors)}")
    print(f"Total Time (s)    : {total_time:.2f}")
    if latencies:
        print(f"Avg Latency (ms)  : {mean(latencies):.2f}")
        print(f"Median Latency(ms): {median(latencies):.2f}")
        if len(latencies) >= 20:
            p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1]
            print(f"P95 Latency (ms)  : {p95:.2f}")
    print("=" * 60)


def parse_args():
    ap = argparse.ArgumentParser(
        description="Async load tester (an toàn, mặc định dry-run, cần --confirm để chạy thật)"
    )
    ap.add_argument("--url", default="http://127.0.0.1/",
                    help="URL cần test (default: http://127.0.0.1/).")
    ap.add_argument("--requests", type=int, default=100, help="Số request tổng (default: 100).")
    ap.add_argument("--concurrency", type=int, default=10, help="Số worker chạy song song (default: 10).")
    ap.add_argument("--max-inflight", type=int, default=100, help="Giới hạn số request in-flight (default: 100).")
    ap.add_argument("--method", choices=["GET", "POST", "PUT", "DELETE"], default="GET")
    ap.add_argument("--data", help="Nội dung POST/PUT (tùy chọn).")
    ap.add_argument("--headers", help="Headers dạng 'Key:Value;Key2:Value2'")
    ap.add_argument("--request-timeout", type=int, default=30, help="Timeout mỗi request (giây, default: 30).")
    ap.add_argument("--ramp-up", type=float, default=0.0, help="Delay khi tăng worker (giảm sốc tải, default: 0).")
    ap.add_argument("--insecure", action="store_true", help="Bỏ SSL verify.")
    ap.add_argument("--confirm", action="store_true", help="Phải có cờ này mới chạy request thật.")

    args = ap.parse_args()
    return args
if __name__ == "__main__":
    args = parse_args()
    print(f"Target: {args.url}, Requests: {args.requests}, Concurrency: {args.concurrency}")

    if not args.confirm:
        print("\n⚠️ Dry run — chưa gửi request. Dùng --confirm để chạy thật.\n")
    else:
        asyncio.run(run_test(args))

