# sandbox/ 替换为 per-session 的 drafts/{session_id}/

原 `sandbox/` 是单一共享工作区，多窗口同时运行时所有进程的输出（source artifacts、流水线产物、运行时中间文件）写入同一目录，相互覆盖。为支持多开实例完全隔离，将 `sandbox/` 整体替换为 `drafts/{session_id}/`，会话编号格式为 `{timestamp}_{pid}`。每个进程拥有独立的草稿目录，`core/paths.py` 中所有路径常量改为 session 感知。

**代价：** `core/paths.py` 及所有引用沙盒路径的模块必须接受 `session_id` 参数，改动面较大。

**为何不保留 sandbox/ 作快速路径：** 单实例优化会让多开路径成为二等公民，并在代码里制造两套路径逻辑，长期维护成本更高。
