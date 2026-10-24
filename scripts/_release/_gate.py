"""P2 gate 门禁编排：verify+regression 并行、十守护、设计护栏、通过戳。

从 `scripts/release.py` 下沉（入口行数红线），只收显式依赖（`ctx`）：
路径常量、子进程执行器、守护清单与计时器都由入口按当前模块状态注入——
测试对入口属性的 monkeypatch 依旧生效。
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import json
import re
import sys
import time
from pathlib import Path


def tree_fingerprint(exec_fn, root, runner=None) -> str:
    """工作区树指纹：`git diff HEAD` + `git status --porcelain` 的 sha256。

    gate 与 publish 之间只允许出现「文档统计同步」这类幂等写入；指纹不同即说明
    代码/配置变了，publish 不得复用 gate 的 verify 结果。
    """
    rc_diff, diff, _ = exec_fn(["git", "diff", "HEAD"], root, runner)
    rc_status, status, _ = exec_fn(["git", "status", "--porcelain"], root, runner)
    if rc_diff != 0 or rc_status != 0:
        return ""
    return hashlib.sha256((diff + "\n---\n" + status).encode("utf-8")).hexdigest()


#: 影响测试结论的路径（文档改动不算）：bench 与 gate 之间只允许文档变化
CODE_PATHS: tuple[str, ...] = ("src", "scripts", "pyproject.toml", "pytest.ini", "requirements.txt")


def code_file_hashes(exec_fn, root, runner=None) -> dict[str, str] | None:
    """测试相关代码路径的逐文件内容哈希（工作区口径：tracked + 未忽略的未跟踪文件）。

    必须取**内容**而非「相对 HEAD 的差异」：publish 会先把 prepare 的改动提交再算
    指纹，若按 `git diff HEAD` / `git status` 哈希，HEAD 一变同一份代码就得到两个指纹，
    gate 的戳必然对不上、复用路径按构造永不命中。

    Returns:
        {相对路径: sha256 hex}；git 查询失败返回 None（与「没有任何代码文件」区分开）。
    """
    rc, out, _ = exec_fn(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *CODE_PATHS],
        root,
        runner,
    )
    if rc != 0:
        return None
    hashes: dict[str, str] = {}
    for rel in sorted(name for name in out.split("\0") if name):
        try:
            with open(os.path.join(root, rel), "rb") as handle:
                body = handle.read()
        except OSError:
            continue  # 文件在列举与读取之间消失（构建产物等）：跳过即可，不改变口径
        hashes[rel] = hashlib.sha256(body).hexdigest()
    return hashes


def fingerprint_of(hashes: dict[str, str]) -> str:
    """逐文件哈希 → 汇总指纹（空字典仍是稳定指纹，与「git 查询失败」的空串区分）。"""
    digest = hashlib.sha256()
    for rel in sorted(hashes):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(hashes[rel]))
    return digest.hexdigest()


def code_fingerprint(exec_fn, root, runner=None) -> str:
    """测试相关代码路径的**内容**指纹（sha256，与提交状态无关）。

    与 `tree_fingerprint` 的分工：本指纹只关心「会不会改变测试结论」的文件，
    故 evolution / 统计回写这类文档写入不会使其失效——否则发布流程里必然
    出现「刚 bench 完就被文档改写打回」的无谓返工。
    """
    hashes = code_file_hashes(exec_fn, root, runner)
    return "" if hashes is None else fingerprint_of(hashes)


def diff_code_files(recorded: dict[str, str], current: dict[str, str]) -> list[str]:
    """两份「路径 → 哈希」之间的差异文件（新增/删除/内容变化，按路径排序）。"""
    changed = set(recorded) ^ set(current)
    changed |= {rel for rel in set(recorded) & set(current) if recorded[rel] != current[rel]}
    return sorted(changed)


def read_gate_stamp(path) -> dict | None:
    """读 gate 戳原文（不校验匹配；缺文件/坏 JSON 返回 None）。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_bench_stamp(path, version: str, modes: list[str], fingerprint: str, covers_unit: bool) -> None:
    """refresh 的 bench 通过戳：记录实际跑过的模式与代码指纹。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": version,
                "modes": list(modes),
                "covers_unit": bool(covers_unit),
                "code_fingerprint": fingerprint,
                "ts": _dt.datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def bench_covers_verify(path, version: str, fingerprint: str) -> dict | None:
    """bench 戳是否可用于替代 P1 verify。

    三个条件缺一不可：版本一致、实际跑过 `unit`（verify 的严格超集）、
    代码指纹一致（`src/scripts/` 等未变）。任一不满足 → None（调用方实跑 verify）。
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not fingerprint or data.get("version") != version:
        return None
    if not data.get("covers_unit"):
        return None
    if data.get("code_fingerprint") != fingerprint:
        return None
    return data


def write_gate_stamp(
    path,
    version: str,
    fingerprint: str,
    verify_passed: str,
    source: str = "run",
    code_files: dict[str, str] | None = None,
) -> None:
    """写入 gate 通过戳（logs/ 为 git 忽略域，不入目录树/门禁）。

    ``code_files``：gate 时刻的逐文件代码哈希。publish 指纹不匹配时据此点名
    「gate 之后哪些代码文件动过」，把「为什么重跑 verify」说清楚（不是白跑）。
    """
    payload = {
        "version": version,
        "fingerprint": fingerprint,
        "verify_passed": verify_passed,
        "verify_source": source,
        "ts": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    if code_files:
        payload["code_files"] = dict(sorted(code_files.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def gate_stamp_matches(path, version: str, fingerprint: str):
    """指纹与版本都一致时返回戳数据，否则 None（缺文件/坏 JSON/指纹空均视为不匹配）。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not fingerprint or data.get("version") != version or data.get("fingerprint") != fingerprint:
        return None
    return data


def run_gate(args, ctx, runner=None) -> int:
    print("[..] P2 门禁：演进对照新鲜度（当前开发版列头须今日刷新）")
    findings = ctx.check_evolution_freshness(ctx.folders_file.read_text(encoding="utf-8"), _dt.date.today().isoformat())
    if findings:
        for item in findings:
            print(f"[ERR] {item}")
        print("[ERR] 演进对照过期，先执行 scripts/release.py evolution 刷新后重跑 gate")
        return 2
    print("[OK] 演进对照新鲜度通过\n")

    print("[..] P2 门禁：归档迁移前置（该版本已解决表须已迁档且归档节存在）")
    version = ctx.read_app_version(ctx.constants_file.read_text(encoding="utf-8"))
    if version.endswith("-dev"):
        print(f"[ERR] 版本仍是开发版 {version} —— gate 须在 prepare 之后执行")
        return 2
    rf_archive, _ = ctx.ledger_archive_paths(version)
    status, pending = ctx.rf_archive_status(ctx.rf_file.read_text(encoding="utf-8"), version)
    if status == "pending":
        print(f"[ERR] review-findings 该版本仍有 {pending} 条已解决条目未迁档")
        print("[ERR] 先执行 scripts/release.py archive（或人工迁档）后重跑 gate")
        return 2
    if status == "archived":
        archived_ok = rf_archive.exists() and ctx.has_archive_section(rf_archive.read_text(encoding="utf-8"), version)
        if not archived_ok:
            print(f"[ERR] 主台账已留迁档占位，但 {rf_archive.name} 缺 `## v{version} 开发期已修复` 批次节")
            print("[ERR] 先执行 scripts/release.py archive（或人工迁档）后重跑 gate")
            return 2
    else:  # absent：本版没有自审条目，无待迁档内容
        print("[!] 该版本无「开发期已修复」节（无自审条目），跳过归档断言")
    # changelog 归档段非空：prepare 已拦「占位句原样归档」，此处拦旁路/人工归档
    # 写出的「只有标题、没有正文」段——发布记录一旦落盘就再也补不回来
    changelog_archive, _changelog_name = ctx.changelog_archive_paths(version)
    if not changelog_archive.exists():
        print(f"[ERR] 缺少 changelog 归档文件 {changelog_archive.name}")
        print("[ERR] 先执行 scripts/release.py prepare（或 archive）后重跑 gate")
        return 2
    if not ctx.changelog_section_has_entries(changelog_archive.read_text(encoding="utf-8"), version):
        print(f"[ERR] {changelog_archive.name} 的 `## [{version}]` 段没有实际条目（只有标题/占位句）")
        print("[ERR] 发布记录缺内容：先在 changelog 开发段写条目再重跑 prepare")
        return 2
    print("[OK] 归档迁移前置通过\n")

    # P1 verify（全量单元，约 28s）与 P2 regression（场景，约 6s）并行。verify 在
    # 两种情况下可省：① refresh 的 bench 刚跑过 `unit`（verify 的严格超集，由
    # check-test-markers 的「unit_* ⇒ unit」不变量保证）且代码指纹未变；此时只跑回归，
    # 省 28s。否则照常并行实跑——状态缺失/过期一律回落实跑，不盲信。
    bench_stamp = bench_covers_verify(ctx.bench_stamp_file, version, code_fingerprint(ctx.exec_fn, ctx.root, runner))
    print("[..] P2 门禁：P1 verify + 场景回归（并行）")
    from concurrent.futures import ThreadPoolExecutor

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_verify = (
            None
            if bench_stamp
            else pool.submit(
                ctx.exec_fn, [sys.executable, "scripts/test-runner.py", "--mode", "verify"], ctx.root, runner
            )
        )
        fut_regression = pool.submit(
            ctx.exec_fn, [sys.executable, "scripts/test-runner.py", "--mode", "regression"], ctx.root, runner
        )
        if bench_stamp:
            rc_v, out_v, err_v = 0, "", ""
        else:
            rc_v, out_v, err_v = fut_verify.result()
        rc_r, out_r, err_r = fut_regression.result()
    ctx.timer().mark_elapsed("P2 verify+regression（并行）", started)

    verify_source = "bench-unit" if bench_stamp else "run"
    if bench_stamp:
        print("[OK] P1 verify 复用 refresh 的 bench unit（verify 的严格超集，代码指纹一致；bench 已通过）")
    if out_v.strip():
        print(out_v.rstrip())
    if rc_v != 0:
        if err_v.strip():
            print(err_v.rstrip())
        print("[ERR] P1 verify 未通过，P2 中止（合并前拦截，未产生 release 提交）")
        return rc_v if rc_v != 0 else 1
    verify_counts = re.findall(r"(\d[\d,]*) 通过", out_v)
    verify_passed = verify_counts[-1].replace(",", "") if verify_counts else ""
    if not bench_stamp:
        print(f"[OK] P1 verify 通过（{verify_passed or '见报告'} 项）")

    if out_r.strip():
        print(out_r.rstrip())
    if rc_r != 0:
        if err_r.strip():
            print(err_r.rstrip())
        print("[ERR] 场景回归未通过，P2 中止")
        return rc_r if rc_r != 0 else 1
    print("[OK] 场景回归通过\n")

    workers = ctx.gate_workers()
    print(f"[..] P2 门禁：十守护 --ci（{workers} 路并行）")
    from concurrent.futures import ThreadPoolExecutor

    started = time.perf_counter()
    worst = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # 全部守护为 --ci 只读子进程（不写业务文件；结论缓存为每 namespace 独立
        # 文件、事实缓存为单文件，均原子 temp+rename 写，并行无互踩），按清单序
        # 收集结果，与串行版输出顺序一致，便于门禁日志对拍；并发度见 _gate_workers
        futures = [
            (script, pool.submit(ctx.exec_fn, [sys.executable, script, "--ci"], ctx.root, runner))
            for script in ctx.guard_scripts
        ]
        for script, fut in futures:
            rc, out, err = fut.result()
            if rc == 0:
                print(f"  [OK] {Path(script).name}")
            else:
                print(f"  [ERR] {Path(script).name}（退出码 {rc}）")
                if out.strip():
                    print("    " + out.strip().replace("\n", "\n    "))
                if err.strip():
                    print("    " + err.strip().replace("\n", "\n    "))
                worst = max(worst, rc) if rc in (1, 2, 3) else 1
    ctx.timer().mark_elapsed("P2 十守护", started, workers=workers)
    if worst:
        print("[ERR] P2 守护存在 finding，先修复再发布")
        return worst

    # 设计护栏（不入十守护清单——清单为 pre-commit/CI guards 五处同源硬约定；
    # 发布门禁域单独纳入：E 级拦 / W 级观察统计，开发期快反馈由 unit 测试承担）
    print("[..] P2 门禁：设计护栏（check-style-guardrails，E 级拦 / W 级观察统计）")
    started = time.perf_counter()
    rc, out, err = ctx.exec_fn([sys.executable, "scripts/check-style-guardrails.py", "--ci"], ctx.root, runner)
    ctx.timer().mark_elapsed("P2 设计护栏", started)
    if out.strip():
        print("  " + out.strip().replace("\n", "\n  "))
    if rc != 0:
        if err.strip():
            print("  " + err.strip().replace("\n", "\n  "))
        print("[ERR] 设计护栏未通过，P2 中止")
        return rc if rc in (1, 2, 3) else 1
    print("[OK] 设计护栏通过\n")

    if getattr(args, "with_portability", False):
        print("[..] P2 门禁：portability 探针（CI portability job 的本地等价复现）")
        started = time.perf_counter()
        rc, out, err = ctx.exec_fn(
            [sys.executable, "scripts/test-runner.py", "--mode", "portability"], ctx.root, runner
        )
        ctx.timer().mark_elapsed("P2 portability", started)
        if out.strip():
            print(out.rstrip())
        if rc != 0:
            if err.strip():
                print(err.rstrip())
            print("[ERR] portability 探针未通过，P2 中止")
            return rc if rc in (1, 2, 3) else 1
        print("[OK] portability 探针通过\n")

    # 用**代码指纹**（而非全树）：verify 的结论只取决于 src/scripts/ 等测试相关路径，
    # 发布链里的文档统计同步不应让 gate 刚跑完的 verify 失效（否则 publish 必定重跑）
    code_files = code_file_hashes(ctx.exec_fn, ctx.root, runner)
    fingerprint = "" if code_files is None else fingerprint_of(code_files)
    write_gate_stamp(
        ctx.stamp_file, version, fingerprint, verify_passed, source=verify_source, code_files=code_files or {}
    )
    suffix = " + portability" if getattr(args, "with_portability", False) else ""
    print(f"[OK] P2 门禁全绿（演进新鲜度 + verify + regression + 十守护 + 设计护栏{suffix}）")
    print(f"[OK] gate 通过戳已写入（指纹 {fingerprint[:12]}…），publish 指纹一致时复用 P1 verify")
    return 0


# ─────────────────────────── publish / devbump ───────────────────────────
