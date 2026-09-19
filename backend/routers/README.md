# routers 模块化设计说明

V1.0.0 当前保留 routers 目录，用于后续将 main.py 中的接口逐步拆分。

建议拆分方向：

```text
routers/
├── dashboard.py
├── inspection.py
├── qa.py
├── records.py
├── devices.py
├── rag.py
├── evaluation.py
├── hardware.py
├── defense.py
└── paper.py
```

当前版本先保留兼容式 main.py，避免一次性重构导致已有接口不稳定。
后续可以逐步把接口移动到各 router 文件中。
