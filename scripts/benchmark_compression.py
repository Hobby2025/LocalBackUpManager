#!/usr/bin/env python3
# 압축 알고리즘 벤치마크 스크립트 (CRLF)
# - 외부 의존성 추가 없이 표준 라이브러리와 zstd/lz4 외부 바이너리를 활용
# - 사용법: python scripts/benchmark_compression.py --input <파일경로> [--algos gzip,zstd,lz4] [--levels 1,3,5,7,9]

import argparse
import os
import time
import shutil
import subprocess
import json
from pathlib import Path

# 한국어 로그 출력 유틸
def log(msg: str) -> None:
    print(f"[bench] {msg}")


def compress_gzip(src: Path, level: int) -> Path:
    import gzip
    dst = Path(str(src) + f".gz")
    start = time.time()
    with open(src, 'rb') as f_in:
        with gzip.open(dst, 'wb', compresslevel=max(1, min(level, 9))) as f_out:
            shutil.copyfileobj(f_in, f_out)
    duration = time.time() - start
    return dst, duration


def compress_zstd(src: Path, level: int) -> Path:
    dst = Path(str(src) + f".zst")
    if not shutil.which('zstd'):
        raise RuntimeError('zstd 실행 파일을 찾을 수 없습니다.')
    start = time.time()
    cmd = ['zstd', f'-{max(1, min(level, 19))}', '-T0', '-f', str(src), '-o', str(dst)]
    c = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duration = time.time() - start
    if c.returncode != 0:
        raise RuntimeError(f"zstd 실패: {c.stderr}")
    return dst, duration


def compress_lz4(src: Path, level: int) -> Path:
    dst = Path(str(src) + f".lz4")
    if not shutil.which('lz4'):
        raise RuntimeError('lz4 실행 파일을 찾을 수 없습니다.')
    start = time.time()
    # lz4 -<level> -f <src> <dst>
    cmd = ['lz4', f'-{max(1, min(level, 12))}', '-f', str(src), str(dst)]
    c = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duration = time.time() - start
    if c.returncode != 0:
        raise RuntimeError(f"lz4 실패: {c.stderr}")
    return dst, duration


def human(n: int) -> str:
    units = ['B', 'KB', 'MB', 'GB']
    s = float(n)
    for u in units:
        if s < 1024.0:
            return f"{s:.2f} {u}"
        s /= 1024.0
    return f"{s:.2f} TB"


def main() -> None:
    p = argparse.ArgumentParser(description='압축 알고리즘 벤치마크')
    p.add_argument('--input', required=True, help='입력 파일 경로')
    p.add_argument('--algos', default='gzip,zstd,lz4', help='대상 알고리즘 CSV(gzip,zstd,lz4)')
    p.add_argument('--levels', default='1,3,5,7,9', help='레벨 CSV(정수)')
    p.add_argument('--keep', action='store_true', help='출력 파일 유지(기본은 삭제)')
    p.add_argument('--report', default='', help='결과 리포트를 저장할 경로(확장자 .csv 또는 .json 권장)')
    p.add_argument('--report-format', default='', help='리포트 포맷 지정(csv|json). 비우면 확장자로 추론')
    args = p.parse_args()

    src = Path(args.input)
    if not src.exists() or not src.is_file():
        raise SystemExit('입력 파일을 찾을 수 없습니다.')

    algos = [a.strip().lower() for a in args.algos.split(',') if a.strip()]
    levels = []
    for t in args.levels.split(','):
        t = t.strip()
        if not t:
            continue
        try:
            levels.append(int(t))
        except Exception:
            pass
    if not levels:
        levels = [1, 3, 5, 7, 9]

    log(f"입력 파일: {src} ({human(src.stat().st_size)})")
    log(f"대상 알고리즘: {algos}")
    log(f"레벨: {levels}")
    print()

    results = []
    for algo in algos:
        for lvl in levels:
            try:
                if algo == 'gzip':
                    out, dur = compress_gzip(src, lvl)
                elif algo == 'zstd':
                    out, dur = compress_zstd(src, lvl)
                elif algo == 'lz4':
                    out, dur = compress_lz4(src, lvl)
                else:
                    log(f"알 수 없는 알고리즘: {algo}")
                    continue
                size = out.stat().st_size
                ratio = round((size / src.stat().st_size) * 100, 2) if src.stat().st_size else 0
                log(f"{algo.upper()} Lv{lvl}: {human(size)} ({ratio}%), {dur:.2f}s, 파일: {out.name}")
                results.append({
                    'algorithm': algo,
                    'level': lvl,
                    'compressed_size': size,
                    'compressed_size_human': human(size),
                    'ratio_percent': ratio,
                    'duration_seconds': round(dur, 4),
                    'output_name': out.name,
                })
                if not args.keep:
                    try:
                        out.unlink()
                    except Exception:
                        pass
            except Exception as e:
                log(f"{algo.upper()} Lv{lvl} 실패: {e}")
        print()

    # 리포트 저장 옵션 처리
    if args.report:
        report_path = Path(args.report)
        fmt = (args.report_format or '').lower()
        if not fmt:
            ext = report_path.suffix.lower()
            if ext == '.csv':
                fmt = 'csv'
            elif ext == '.json':
                fmt = 'json'
            else:
                fmt = 'csv'
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            if fmt == 'json':
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump({'input': str(src), 'results': results}, f, ensure_ascii=False, indent=2)
                log(f"JSON 리포트 저장: {report_path}")
            else:
                # CSV 저장(표준 라이브러리 사용)
                import csv
                with open(report_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['algorithm', 'level', 'compressed_size', 'compressed_size_human', 'ratio_percent', 'duration_seconds', 'output_name'])
                    for r in results:
                        writer.writerow([r['algorithm'], r['level'], r['compressed_size'], r['compressed_size_human'], r['ratio_percent'], r['duration_seconds'], r['output_name']])
                log(f"CSV 리포트 저장: {report_path}")
        except Exception as e:
            log(f"리포트 저장 실패: {e}")


if __name__ == '__main__':
    main()
