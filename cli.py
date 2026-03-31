"""WSN Framework CLI — wsn [command] [options]"""
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from wsn_framework.framework import WSNFramework
from wsn_framework.protocols.builtin import REGISTRY


@click.group()
@click.option("--log-level", default="INFO",
              type=click.Choice(["DEBUG","INFO","WARNING","ERROR"]),
              show_default=True, help="로깅 레벨")
def main(log_level):
    """WSN Framework — NS3 + Python 통합 시뮬레이션 환경"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


# ── run ───────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config",  "-c", required=True,
              help="시나리오 YAML 파일 경로")
@click.option("--protocol","-p", required=True,
              type=click.Choice(list(REGISTRY.keys()), case_sensitive=False),
              help="실행할 프로토콜")
@click.option("--reps",    "-r", default=None, type=int,
              help="Monte Carlo 반복 횟수 (미설정 시 YAML 값 사용)")
@click.option("--output",  "-o", default="results",
              show_default=True, help="결과 저장 디렉토리")
def run(config, protocol, reps, output):
    """단일 프로토콜 Monte Carlo 실험 실행"""
    fw = WSNFramework.from_yaml(config, output_dir=output)
    agg = fw.run(protocol, repetitions=reps)
    click.echo(f"\n✓  {protocol}  FND={agg.fnd_mean:.0f}  "
               f"HND={agg.hnd_mean:.0f}  PDR={agg.pdr_mean:.4f}")
    fw.export_all({protocol: agg})


# ── compare ───────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config",    "-c", required=True,
              help="시나리오 YAML 파일 경로")
@click.option("--protocols", "-p", default="LEACH,HEED,PEGASIS,SEP",
              show_default=True,
              help="비교할 프로토콜 목록 (쉼표 구분)")
@click.option("--reps",      "-r", default=None, type=int,
              help="Monte Carlo 반복 횟수")
@click.option("--output",    "-o", default="results",
              show_default=True, help="결과 저장 디렉토리")
def compare(config, protocols, reps, output):
    """여러 프로토콜을 동일 환경에서 비교"""
    proto_list = [p.strip().upper() for p in protocols.split(",")]
    fw = WSNFramework.from_yaml(config, output_dir=output)
    results = fw.compare(proto_list, repetitions=reps)
    fw.print_summary(results)
    fw.export_all(results)
    click.echo(f"\n✓  결과 저장 완료 → {output}/")


# ── sweep ─────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config",    "-c", required=True,
              help="시나리오 YAML 파일 경로")
@click.option("--protocols", "-p", default="LEACH,HEED,SEP",
              show_default=True)
@click.option("--param",     required=True,
              help="변경할 파라미터 (예: topology.num_nodes)")
@click.option("--values",    required=True,
              help="파라미터 값 목록 (쉼표 구분, 예: 50,100,200,500)")
@click.option("--output",    "-o", default="results/sweep",
              show_default=True)
def sweep(config, protocols, param, values, output):
    """파라미터 스윕 실험"""
    proto_list = [p.strip().upper() for p in protocols.split(",")]
    val_list   = [_cast(v) for v in values.split(",")]
    fw = WSNFramework.from_yaml(config, output_dir=output)
    fw.sweep(proto_list, param, val_list)
    click.echo(f"\n✓  스윕 완료 → {output}/")


# ── topology ─────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config", "-c", required=True,
              help="시나리오 YAML 파일 경로")
@click.option("--output", "-o", default="results/figures/topology.png",
              show_default=True)
def topology(config, output):
    """초기 토폴로지 그림 파일만 생성 (시뮬레이션 없음)"""
    fw = WSNFramework.from_yaml(config)
    path = fw.save_topology(output_path=output)
    click.echo(f"✓  토폴로지 저장 → {path}")


# ── list-protocols ────────────────────────────────────────────────────────────

@main.command(name="list-protocols")
def list_protocols():
    """등록된 프로토콜 목록 출력"""
    click.echo("\n등록된 프로토콜:")
    for name in REGISTRY:
        click.echo(f"  • {name}")
    click.echo()


# ── helpers ───────────────────────────────────────────────────────────────────

def _cast(v: str):
    try: return int(v)
    except ValueError: pass
    try: return float(v)
    except ValueError: pass
    return v


if __name__ == "__main__":
    main()
