"""性能基准报告渲染包：`test-perf-report.py` 的报告生成段与样本规模契约。

采样/基准主流程留在入口（依赖离线桩与真实管线），报告渲染是纯文本组装，
独立后入口只留采样与门禁判定。入口按原面 re-export，测试与调用方仍以
`test_perf_report.write_perf_report` 访问。
"""
