#!/usr/bin/env python3
"""
다중 DB 통합 테스트 실행 스크립트
- 환경별 테스트 실행
- 테스트 결과 리포트 생성
- 성능 벤치마크 실행

사용법:
    python scripts/run_multidb_tests.py --suite integration
    python scripts/run_multidb_tests.py --suite performance --output-dir ./reports
    python scripts/run_multidb_tests.py --suite regression --verbose
"""

import os
import sys
import argparse
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class TestRunner:
    """테스트 실행기"""
    
    def __init__(self, output_dir: Optional[Path] = None, verbose: bool = False):
        self.output_dir = output_dir or Path("./test_reports")
        self.verbose = verbose
        self.results = {}
        
        # 출력 디렉토리 생성
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 프로젝트 루트 디렉토리
        self.project_root = Path(__file__).parent.parent
        
    def log(self, message: str, level: str = "INFO"):
        """로그 출력"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
        if self.verbose or level in ["ERROR", "WARNING"]:
            sys.stdout.flush()
    
    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> Dict[str, Any]:
        """명령어 실행"""
        if cwd is None:
            cwd = self.project_root
            
        self.log(f"실행 중: {' '.join(cmd)}")
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            
            duration = time.time() - start_time
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
                "command": " ".join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out after 5 minutes",
                "duration": duration,
                "command": " ".join(cmd)
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": duration,
                "command": " ".join(cmd)
            }
    
    def run_integration_tests(self) -> Dict[str, Any]:
        """통합 테스트 실행"""
        self.log("=== 다중 DB 통합 테스트 시작 ===")
        
        test_files = [
            "tests/test_multidb_integration.py",
        ]
        
        results = {}
        
        for test_file in test_files:
            self.log(f"실행 중: {test_file}")
            
            cmd = [
                "python", "-m", "pytest",
                test_file,
                "-v",
                "--tb=short",
                f"--junitxml={self.output_dir}/junit_{Path(test_file).stem}.xml",
                f"--html={self.output_dir}/report_{Path(test_file).stem}.html",
                "--self-contained-html"
            ]
            
            if self.verbose:
                cmd.append("-s")
            
            result = self.run_command(cmd)
            results[test_file] = result
            
            if result["success"]:
                self.log(f"✅ {test_file} 테스트 성공")
            else:
                self.log(f"❌ {test_file} 테스트 실패", "ERROR")
                if self.verbose:
                    self.log(f"STDOUT: {result['stdout']}")
                    self.log(f"STDERR: {result['stderr']}")
        
        return results
    
    def run_performance_tests(self) -> Dict[str, Any]:
        """성능 테스트 실행"""
        self.log("=== 성능/부하 테스트 시작 ===")
        
        test_files = [
            "tests/test_performance_benchmarks.py",
        ]
        
        results = {}
        
        for test_file in test_files:
            self.log(f"실행 중: {test_file}")
            
            cmd = [
                "python", "-m", "pytest",
                test_file,
                "-v", "-s",
                "--tb=short",
                f"--junitxml={self.output_dir}/junit_performance.xml",
                f"--html={self.output_dir}/report_performance.html",
                "--self-contained-html",
                "--benchmark-only",  # 벤치마크만 실행
                "--benchmark-sort=mean"
            ]
            
            result = self.run_command(cmd)
            results[test_file] = result
            
            if result["success"]:
                self.log(f"✅ {test_file} 성능 테스트 완료")
                # 성능 결과 파싱
                self._parse_performance_results(result["stdout"])
            else:
                self.log(f"❌ {test_file} 성능 테스트 실패", "ERROR")
        
        return results
    
    def run_regression_tests(self) -> Dict[str, Any]:
        """회귀 테스트 실행"""
        self.log("=== PostgreSQL 회귀 테스트 시작 ===")
        
        test_files = [
            "tests/test_regression_postgresql.py",
        ]
        
        results = {}
        
        for test_file in test_files:
            self.log(f"실행 중: {test_file}")
            
            cmd = [
                "python", "-m", "pytest",
                test_file,
                "-v",
                "--tb=short",
                f"--junitxml={self.output_dir}/junit_regression.xml",
                f"--html={self.output_dir}/report_regression.html",
                "--self-contained-html"
            ]
            
            if self.verbose:
                cmd.append("-s")
            
            result = self.run_command(cmd)
            results[test_file] = result
            
            if result["success"]:
                self.log(f"✅ {test_file} 회귀 테스트 통과")
            else:
                self.log(f"❌ {test_file} 회귀 테스트 실패 - 기존 기능에 영향 있음!", "ERROR")
        
        return results
    
    def run_coverage_analysis(self) -> Dict[str, Any]:
        """코드 커버리지 분석"""
        self.log("=== 코드 커버리지 분석 ===")
        
        cmd = [
            "python", "-m", "pytest",
            "tests/",
            "--cov=app",
            "--cov-report=html:" + str(self.output_dir / "coverage_html"),
            "--cov-report=xml:" + str(self.output_dir / "coverage.xml"),
            "--cov-report=term-missing",
            "--cov-fail-under=80"  # 80% 이상 커버리지 요구
        ]
        
        result = self.run_command(cmd)
        
        if result["success"]:
            self.log("✅ 코드 커버리지 분석 완료")
            # 커버리지 결과 파싱
            self._parse_coverage_results(result["stdout"])
        else:
            self.log("❌ 코드 커버리지 기준 미달", "WARNING")
        
        return {"coverage": result}
    
    def _parse_performance_results(self, stdout: str):
        """성능 테스트 결과 파싱"""
        lines = stdout.split('\n')
        performance_data = {}
        
        for line in lines:
            if "seconds" in line and "MB/s" in line:
                # 성능 메트릭 추출
                if "압축 속도:" in line:
                    speed = line.split("압축 속도:")[1].strip().split()[0]
                    performance_data["compression_speed"] = speed
                elif "소요 시간:" in line:
                    duration = line.split("소요 시간:")[1].strip().split("초")[0]
                    performance_data["backup_duration"] = duration
        
        if performance_data:
            # 성능 결과를 JSON 파일로 저장
            with open(self.output_dir / "performance_metrics.json", "w", encoding="utf-8") as f:
                json.dump(performance_data, f, indent=2, ensure_ascii=False)
    
    def _parse_coverage_results(self, stdout: str):
        """커버리지 결과 파싱"""
        lines = stdout.split('\n')
        
        for line in lines:
            if "TOTAL" in line and "%" in line:
                # 전체 커버리지 추출
                parts = line.split()
                if len(parts) >= 4:
                    coverage_percent = parts[-1].rstrip('%')
                    self.log(f"📊 전체 코드 커버리지: {coverage_percent}%")
                    
                    # 커버리지 결과 저장
                    coverage_data = {
                        "total_coverage": coverage_percent,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    with open(self.output_dir / "coverage_summary.json", "w") as f:
                        json.dump(coverage_data, f, indent=2)
    
    def generate_summary_report(self, all_results: Dict[str, Any]):
        """종합 테스트 리포트 생성"""
        self.log("=== 종합 테스트 리포트 생성 ===")
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        total_duration = 0
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "test_suites": {},
            "summary": {}
        }
        
        for suite_name, suite_results in all_results.items():
            suite_summary = {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "duration": 0,
                "tests": {}
            }
            
            for test_file, result in suite_results.items():
                suite_summary["tests"][test_file] = {
                    "success": result["success"],
                    "duration": result["duration"],
                    "command": result["command"]
                }
                
                suite_summary["total"] += 1
                suite_summary["duration"] += result["duration"]
                
                if result["success"]:
                    suite_summary["passed"] += 1
                    passed_tests += 1
                else:
                    suite_summary["failed"] += 1
                    failed_tests += 1
                
                total_tests += 1
                total_duration += result["duration"]
            
            summary["test_suites"][suite_name] = suite_summary
        
        # 전체 요약
        summary["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "total_duration": total_duration
        }
        
        # JSON 리포트 저장
        with open(self.output_dir / "test_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # 텍스트 리포트 생성
        self._generate_text_report(summary)
        
        # 결과 출력
        self.log(f"📊 테스트 결과: {passed_tests}/{total_tests} 통과 ({summary['summary']['success_rate']:.1f}%)")
        self.log(f"⏱️  총 소요 시간: {total_duration:.2f}초")
        self.log(f"📁 리포트 저장 위치: {self.output_dir}")
    
    def _generate_text_report(self, summary: Dict[str, Any]):
        """텍스트 형태 리포트 생성"""
        report_lines = [
            "# 다중 DB 백업 시스템 테스트 리포트",
            f"생성 시간: {summary['timestamp']}",
            "",
            "## 전체 요약",
            f"- 총 테스트: {summary['summary']['total_tests']}개",
            f"- 성공: {summary['summary']['passed_tests']}개",
            f"- 실패: {summary['summary']['failed_tests']}개",
            f"- 성공률: {summary['summary']['success_rate']:.1f}%",
            f"- 총 소요 시간: {summary['summary']['total_duration']:.2f}초",
            ""
        ]
        
        for suite_name, suite_data in summary["test_suites"].items():
            report_lines.extend([
                f"## {suite_name} 테스트 스위트",
                f"- 테스트 수: {suite_data['total']}개",
                f"- 성공: {suite_data['passed']}개",
                f"- 실패: {suite_data['failed']}개",
                f"- 소요 시간: {suite_data['duration']:.2f}초",
                ""
            ])
            
            for test_file, test_result in suite_data["tests"].items():
                status = "✅ 성공" if test_result["success"] else "❌ 실패"
                report_lines.append(f"  - {test_file}: {status} ({test_result['duration']:.2f}초)")
            
            report_lines.append("")
        
        # 파일로 저장
        with open(self.output_dir / "test_report.md", "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))


def main():
    parser = argparse.ArgumentParser(description="다중 DB 통합 테스트 실행기")
    parser.add_argument(
        "--suite",
        choices=["integration", "performance", "regression", "coverage", "all"],
        default="all",
        help="실행할 테스트 스위트"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./test_reports"),
        help="테스트 결과 출력 디렉토리"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 출력 모드"
    )
    
    args = parser.parse_args()
    
    # 테스트 실행기 초기화
    runner = TestRunner(output_dir=args.output_dir, verbose=args.verbose)
    
    runner.log("🚀 다중 DB 백업 시스템 테스트 시작")
    runner.log(f"📁 결과 저장 위치: {args.output_dir}")
    
    all_results = {}
    
    try:
        if args.suite in ["integration", "all"]:
            all_results["integration"] = runner.run_integration_tests()
        
        if args.suite in ["performance", "all"]:
            all_results["performance"] = runner.run_performance_tests()
        
        if args.suite in ["regression", "all"]:
            all_results["regression"] = runner.run_regression_tests()
        
        if args.suite in ["coverage", "all"]:
            all_results["coverage"] = runner.run_coverage_analysis()
        
        # 종합 리포트 생성
        if all_results:
            runner.generate_summary_report(all_results)
        
        runner.log("✅ 모든 테스트 완료")
        
        # 실패한 테스트가 있으면 종료 코드 1 반환
        total_failed = sum(
            sum(1 for result in suite_results.values() if not result.get("success", True))
            for suite_results in all_results.values()
            if isinstance(suite_results, dict)
        )
        
        if total_failed > 0:
            runner.log(f"❌ {total_failed}개 테스트 실패", "ERROR")
            sys.exit(1)
        else:
            runner.log("🎉 모든 테스트 성공!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        runner.log("⚠️  사용자에 의해 테스트 중단", "WARNING")
        sys.exit(130)
    except Exception as e:
        runner.log(f"💥 테스트 실행 중 오류 발생: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
