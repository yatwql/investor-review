"""测试：test-runner 机器信息采集的探测与降级分支（`_test_runner/machine_info.py`）。

补充 `test_test_runner_machine_info.py` 只覆盖「字段形状 / 缺 /proc 回退」之外的路径：
  - Linux 读 `/proc/cpuinfo`、`/proc/meminfo`、`/proc/mounts` 的**解析结果**（物理核去重、
    MemTotal 换算、根分区文件系统、NVMe / 旋转盘 / SSD 判定、sysfs 缺失降级）
  - 解析失败降级：cpuinfo 无 model name、MemTotal 非数字
  - macOS `sysctl` 探测：命令缺失 / 执行异常 / 非零退出 / 取值成功
  - Windows 内存与 CPU 型号采集（ctypes 不可用的非 Windows 解释器上返回 None）
  - `_collect_machine_info` 的 Darwin / Windows 分派（不依赖真实平台）
  - 环境表未知属性、格式化的「仅逻辑线程」分支、`--machine-info` 报告输出与超时标注

采集函数用模块级 `open` 桩喂入固定 `/proc` 内容，`sysctl`/`subprocess`/`ctypes` 全部打桩，
不读取真实硬件、不执行子进程。
"""

from __future__ import annotations

import io
import subprocess
import types

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def mi():
    """机器信息实现（入口脚本已把 scripts/ 载入，子包可直接导入）。"""
    load_script("test-runner.py")
    from _test_runner import machine_info  # pyright: ignore[reportMissingImports]  # scripts/ 由 load_script 注入 sys.path

    return machine_info


def _fake_open(monkeypatch, mi, files: dict[str, str]):
    """把模块视角的 `open` 换成按下表返回内容的桩（缺失路径抛 FileNotFoundError）。"""

    def _open(path, *_args, **_kwargs):
        key = str(path)
        if key in files:
            return io.StringIO(files[key])
        raise FileNotFoundError(key)

    monkeypatch.setattr(mi, "open", _open, raising=False)


class TestLinuxProcParsing:
    """`/proc` 与 `/sys` 解析结果（固定内容喂入，不读真实硬件）。"""

    def test_cpu_model_from_cpuinfo(self, mi, monkeypatch):
        """取 `model name` 行的值。"""
        _fake_open(monkeypatch, mi, {"/proc/cpuinfo": "processor\t: 0\nmodel name\t: AMD Ryzen 9 5900X\n"})
        assert mi._read_cpu_model_linux() == "AMD Ryzen 9 5900X"

    def test_cpu_model_absent_returns_none(self, mi, monkeypatch):
        """cpuinfo 存在但没有 `model name` 行 → None（不抛异常、不返回空串）。"""
        _fake_open(monkeypatch, mi, {"/proc/cpuinfo": "processor\t: 0\ncpu MHz\t: 3600.000\n"})
        assert mi._read_cpu_model_linux() is None

    def test_physical_cores_dedup_by_id_pair(self, mi, monkeypatch):
        """按 (physical id, core id) 去重：超线程的重复 core id 不重复计数。"""
        cpuinfo = (
            "processor\t: 0\nphysical id\t: 0\ncore id\t: 0\n"
            "\n"
            "processor\t: 1\nphysical id\t: 0\ncore id\t: 0\n"
            "\n"
            "processor\t: 2\nphysical id\t: 0\ncore id\t: 1\n"
        )
        _fake_open(monkeypatch, mi, {"/proc/cpuinfo": cpuinfo})
        assert mi._count_physical_cores_linux() == 2

    def test_physical_cores_empty_returns_none(self, mi, monkeypatch):
        """cpuinfo 无核信息 → None（调用方按「未知」展示）。"""
        _fake_open(monkeypatch, mi, {"/proc/cpuinfo": "\n\n"})
        assert mi._count_physical_cores_linux() is None

    def test_mem_total_converted_to_gib(self, mi, monkeypatch):
        """`MemTotal` 按 KB → GiB 换算。"""
        _fake_open(monkeypatch, mi, {"/proc/meminfo": "MemTotal:        8388608 kB\nMemFree: 1 kB\n"})
        assert mi._mem_gib_linux() == pytest.approx(8.0)

    def test_mem_total_non_numeric_returns_none(self, mi, monkeypatch):
        """`MemTotal` 值非数字 → None（解析失败不冒泡成崩溃）。"""
        _fake_open(monkeypatch, mi, {"/proc/meminfo": "MemTotal:        not-a-number kB\n"})
        assert mi._mem_gib_linux() is None

    def test_missing_mem_total_line_returns_none(self, mi, monkeypatch):
        """meminfo 里没有 MemTotal 行 → None（循环跑完自然返回，非异常路径）。"""
        _fake_open(monkeypatch, mi, {"/proc/meminfo": "MemFree: 1024 kB\n"})
        assert mi._mem_gib_linux() is None

    def test_nvme_root_disk_detected(self, mi, monkeypatch):
        """根分区在 nvme 设备上 → 直接判 NVMe SSD，不去读 sysfs。"""
        _fake_open(monkeypatch, mi, {"/proc/mounts": "/dev/nvme0n1p2 / ext4 rw,relatime 0 0\n"})
        assert mi._linux_disk_info() == ("ext4", "NVMe SSD")

    @pytest.mark.parametrize(("rotational", "expected"), [("1\n", "HDD"), ("0\n", "SSD")])
    def test_rotational_flag_decides_hdd_or_ssd(self, mi, monkeypatch, rotational, expected):
        """sysfs `rotational` 为 1 判 HDD、为 0 判 SSD（分区尾号先剥掉再拼路径）。"""
        _fake_open(
            monkeypatch,
            mi,
            {
                "/proc/mounts": "/dev/sda1 / ext4 rw 0 0\n",
                "/sys/block/sda/queue/rotational": rotational,
            },
        )
        assert mi._linux_disk_info() == ("ext4", expected)

    def test_missing_sysfs_rotational_degrades_to_unknown_disk(self, mi, monkeypatch):
        """sysfs 不可读（容器常见）→ 磁盘类型未知，但文件系统仍返回。"""
        _fake_open(monkeypatch, mi, {"/proc/mounts": "/dev/sda1 / ext4 rw 0 0\n"})
        assert mi._linux_disk_info() == ("ext4", None)

    def test_no_root_mount_line_yields_unknowns(self, mi, monkeypatch):
        """`/proc/mounts` 里没有 `/` 行 → 两者皆 None。"""
        _fake_open(monkeypatch, mi, {"/proc/mounts": "/dev/sdb1 /data ext4 rw 0 0\n"})
        assert mi._linux_disk_info() == (None, None)


class TestSysctlProbe:
    """macOS `sysctl` 探测：命令缺失 / 执行异常 / 非零退出 / 成功。"""

    def _install_subprocess(self, mi, monkeypatch, proc=None, exc: BaseException | None = None) -> None:
        def _run(*_args, **_kwargs):
            if exc is not None:
                raise exc
            return proc

        monkeypatch.setattr(
            mi, "subprocess", types.SimpleNamespace(run=_run, SubprocessError=subprocess.SubprocessError)
        )

    def test_missing_sysctl_command_returns_none(self, mi, monkeypatch):
        """非 macOS 上 `sysctl` 不存在 → None，不尝试执行。"""
        monkeypatch.setattr(mi, "shutil", types.SimpleNamespace(which=lambda _name: None))
        assert mi._sysctl_value("hw.memsize") is None

    def test_subprocess_error_returns_none(self, mi, monkeypatch):
        """执行异常（OSError/SubprocessError）→ None。"""
        monkeypatch.setattr(mi, "shutil", types.SimpleNamespace(which=lambda _name: "/usr/sbin/sysctl"))
        self._install_subprocess(mi, monkeypatch, exc=OSError("boom"))
        assert mi._sysctl_value("hw.memsize") is None

    def test_nonzero_exit_returns_none(self, mi, monkeypatch):
        """sysctl 未知键会非零退出 → None（不把错误文本当值）。"""
        monkeypatch.setattr(mi, "shutil", types.SimpleNamespace(which=lambda _name: "/usr/sbin/sysctl"))
        self._install_subprocess(mi, monkeypatch, proc=subprocess.CompletedProcess([], 1, "", "unknown oid"))
        assert mi._sysctl_value("hw.unknown") is None

    def test_successful_value_is_trimmed(self, mi, monkeypatch):
        """成功取值去首尾空白。"""
        monkeypatch.setattr(mi, "shutil", types.SimpleNamespace(which=lambda _name: "/usr/sbin/sysctl"))
        self._install_subprocess(mi, monkeypatch, proc=subprocess.CompletedProcess([], 0, "  17179869184\n", ""))
        assert mi._sysctl_value("hw.memsize") == "17179869184"


class TestWindowsMemoryProbe:
    """`_mem_gib_windows`：ctypes 全局内存状态读取与不可用降级。"""

    def test_reads_total_physical_memory(self, mi, monkeypatch):
        """`GlobalMemoryStatusEx` 成功时按 ullTotalPhys 换算 GiB。"""
        import ctypes

        def _global_memory_status(ref) -> int:
            ref._obj.ullTotalPhys = 34359738368  # 32 GiB
            return 1

        stub = types.SimpleNamespace(kernel32=types.SimpleNamespace(GlobalMemoryStatusEx=_global_memory_status))
        monkeypatch.setattr(ctypes, "windll", stub, raising=False)
        assert mi._mem_gib_windows() == pytest.approx(32.0)

    def test_failure_of_api_call_returns_none(self, mi, monkeypatch):
        """API 返回 0（调用失败）→ None。"""
        import ctypes

        stub = types.SimpleNamespace(kernel32=types.SimpleNamespace(GlobalMemoryStatusEx=lambda _ref: 0))
        monkeypatch.setattr(ctypes, "windll", stub, raising=False)
        assert mi._mem_gib_windows() is None

    def test_oserror_during_probe_returns_none(self, mi, monkeypatch):
        """探测抛 OSError（受限环境拦 API）→ None，不让采集整体失败。"""
        import ctypes

        def _raise(_ref):
            raise OSError("blocked")

        stub = types.SimpleNamespace(kernel32=types.SimpleNamespace(GlobalMemoryStatusEx=_raise))
        monkeypatch.setattr(ctypes, "windll", stub, raising=False)
        assert mi._mem_gib_windows() is None


class TestPlatformDispatch:
    """`_collect_machine_info` 按平台走不同采集支路。"""

    def _platform(self, mi, monkeypatch, system: str, processor: str = "") -> None:
        monkeypatch.setattr(
            mi,
            "platform",
            types.SimpleNamespace(
                system=lambda: system,
                release=lambda: "release-x",
                machine=lambda: "arm64",
                python_version=lambda: "3.13.5",
                processor=lambda: processor,
            ),
        )

    def test_darwin_branch_parses_sysctl_values(self, mi, monkeypatch):
        """Darwin：CPU 型号/物理核/内存都来自 sysctl，数字串转 int。"""
        self._platform(mi, monkeypatch, "Darwin")
        values = {
            "machdep.cpu.brand_string": "Apple M2 Pro",
            "hw.physicalcpu": "12",
            "hw.memsize": str(32 * 1024**3),
        }
        monkeypatch.setattr(mi, "_sysctl_value", lambda name: values.get(name))
        monkeypatch.setattr(mi, "os", types.SimpleNamespace(cpu_count=lambda: 12))

        info = mi._collect_machine_info("low", bench_jobs=2)

        assert info["cpu_model"] == "Apple M2 Pro"
        assert info["cpu_physical_cores"] == 12
        assert info["mem_gib"] == pytest.approx(32.0)
        assert info["arch"] == "arm64"
        assert info["bench_jobs"] == 2

    def test_darwin_non_numeric_sysctl_degrades_to_none(self, mi, monkeypatch):
        """sysctl 返回非数字（或缺失）→ 相应字段 None，不影响其他字段。"""
        self._platform(mi, monkeypatch, "Darwin")
        monkeypatch.setattr(mi, "_sysctl_value", lambda name: "" if name == "hw.physicalcpu" else None)
        monkeypatch.setattr(mi, "os", types.SimpleNamespace(cpu_count=lambda: 8))

        info = mi._collect_machine_info()

        assert info["cpu_physical_cores"] is None
        assert info["mem_gib"] is None
        assert info["cpu_model"] is None

    def test_windows_branch_uses_processor_and_memory_probe(self, mi, monkeypatch):
        """Windows：CPU 型号取 `platform.processor()`，物理核按逻辑线程近似，内存走 ctypes。"""
        self._platform(mi, monkeypatch, "Windows", processor="Intel(R) Core(TM) i7")
        monkeypatch.setattr(mi, "os", types.SimpleNamespace(cpu_count=lambda: 16))
        monkeypatch.setattr(mi, "_mem_gib_windows", lambda: 64.0)

        info = mi._collect_machine_info()

        assert info["cpu_model"] == "Intel(R) Core(TM) i7"
        assert info["cpu_physical_cores"] == 16
        assert info["mem_gib"] == pytest.approx(64.0)

    def test_windows_empty_processor_falls_back_to_none(self, mi, monkeypatch):
        """`platform.processor()` 为空串时 cpu_model 记 None（不展示空串）。"""
        self._platform(mi, monkeypatch, "Windows", processor="")
        monkeypatch.setattr(mi, "os", types.SimpleNamespace(cpu_count=lambda: 4))
        monkeypatch.setattr(mi, "_mem_gib_windows", lambda: None)

        info = mi._collect_machine_info()

        assert info["cpu_model"] is None
        assert info["mem_gib"] is None


class TestRenderingEdges:
    """渲染边界：未知属性、仅逻辑线程、`--machine-info` 报告输出。"""

    def test_unknown_env_label_returns_none(self, mi):
        """表外属性名 → None 表示不更新该行（转发到表格渲染时不新增垃圾行）。"""
        assert mi._env_value("不存在的属性", {"os": "Linux"}) is None

    def test_format_machine_info_threads_only(self, mi):
        """缺物理核数但有逻辑线程时展示「逻辑 N 线程」。"""
        line = mi._format_machine_info(
            {
                "os": "Linux",
                "arch": "x86_64",
                "cpu_model": "AMD",
                "cpu_physical_cores": None,
                "cpu_threads": 16,
                "mem_gib": 32.0,
                "disk_type": "SSD",
                "python_version": "3.13.5",
                "parallel_level": "high",
                "parallel_workers": "16",
            }
        )
        assert "逻辑 16 线程" in line
        assert "核 " not in line

    def test_format_machine_info_all_counts_unknown(self, mi):
        """物理核与逻辑线程都未知时展示「未知」（不输出 None）。"""
        line = mi._format_machine_info(
            {"os": "Linux", "cpu_physical_cores": None, "cpu_threads": None, "python_version": "3.13.5"}
        )
        assert "· 未知 ·" in line
        assert "None" not in line

    def test_print_report_skipped_when_disabled(self, mi, capsys):
        """未开启 `--machine-info`（None）→ 不输出任何内容。"""
        mi._print_machine_report(None, [{"mode": "unit", "duration": 1.0}])
        assert capsys.readouterr().out == ""

    def test_print_report_outputs_env_and_duration_tables(self, mi, capsys):
        """开启后依次输出机器信息行、环境属性表、耗时表与超时标注。"""
        info = {
            "os": "Linux",
            "arch": "x86_64",
            "cpu_model": "AMD",
            "cpu_physical_cores": 8,
            "cpu_threads": 16,
            "mem_gib": 32.0,
            "disk_type": "SSD",
            "fs_type": "ext4",
            "python_version": "3.13.5",
            "parallel_level": "medium",
            "parallel_workers": "8",
            "bench_jobs": 2,
            "date": "2026-01-01",
        }
        results = [
            {"mode": "unit", "passed": 10, "failed": 1, "duration": 1.4},
            {"mode": "live", "duration": 5.0, "timed_out": True},
        ]

        mi._print_machine_report(info, results)

        out = capsys.readouterr().out
        assert "> 采集环境：Linux x86_64 · AMD · 8 核 16 线程" in out
        assert "| 环境属性 | 值 |" in out
        assert "| `--mode` | 覆盖项数 | 耗时 |" in out
        assert "| `unit` | 11 | ~1s |" in out
        assert "超时未纳入耗时表：live" in out
