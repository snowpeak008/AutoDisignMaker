# AutoDesignMaker — Domain Glossary

> This file is a glossary only. No implementation details, specs, or decisions here.
> Architecture decisions live in `docs/adr/`.

---

## Terms

### 正式存档 (Formal Archive)
A named project directory under `saves/{name}/` containing `manifest.json` and `workspace/`. It is the authoritative, user-facing saved state of a project. Snapshots and runtime artifacts are excluded. A formal archive is created only by an explicit user action ("保存" / "另存为"). It is never written to directly during editing.

### 临时工作区 / 草稿 (Draft Workspace)
A per-session working directory under `drafts/{session_id}/` inside the project folder. All editing happens here. It mirrors the structure of `sandbox/` (source artifacts, outputs, runtime state). Every user action is auto-saved into the draft with a debounce delay. A draft either has a linked formal archive path, or it does not (new/template-based project).

### 关联正式存档路径 (Linked Archive Path)
A field in `draft_meta.json` recording which formal archive this draft corresponds to. Empty string when the project has never been saved (new project or template-based project). Set after first "Save As" succeeds.

### 会话编号 (Session ID)
A string of the form `{timestamp}_{pid}` (e.g. `20260621_153045_12345`) assigned to each process at startup. Determines the draft workspace directory name. The PID component is stored in `draft_meta.json` for liveness detection.

### 内容指纹 (Content Fingerprint)
A single SHA256 string representing the entire project state. Computed by: sorting all files in `workspace/` by relative path, concatenating their individual SHA256 hashes, then taking SHA256 of the result. Used at exit time and during archive conflict checks. Not used for the dirty flag.

### 脏标记 (Dirty Flag)
An in-memory boolean set to `true` on any user action, regardless of whether the content actually changed from the saved state. Controls the enabled/disabled state of the Save button in the UI. Cleared only after a successful save. Not authoritative for exit dialogs — the content fingerprint is.

### 空白初始状态 (Blank Initial State)
The state of a draft workspace where `source_artifacts/` and `outputs/` contain no user data files (only system placeholder files such as `.gitkeep`). A project in this state does not trigger an "unsaved changes" exit dialog.

### 模版 (Template)
A formal archive used as a seed data source. Opening a template copies its `workspace/` contents into a new draft with an empty linked archive path — the template itself is never modified. The first save from a template-based draft always invokes the "Save As" flow, creating a new formal archive.

### 存档锁 (Archive Lock)
A lock file written into a formal archive directory when that archive is opened for editing. Prevents a second session from opening the same archive simultaneously. Released when the editing session ends (normal exit or explicit close). A second window attempting to open a locked archive receives an error and cannot proceed.

### 原子保存 (Atomic Save)
The save procedure that prevents archive corruption: (1) write all content to a sibling temp directory `saves/{name}_tmp/`, (2) verify the content fingerprint matches expectation, (3) delete the old `saves/{name}/` directory, (4) rename `saves/{name}_tmp/` to `saves/{name}/`. On Windows, same-drive directory rename is atomic.
