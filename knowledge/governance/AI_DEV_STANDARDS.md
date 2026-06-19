# AI 游戏工程通用技术基准 V1.0

> **文件路径**：`Docs/governance/AI_DEV_STANDARDS.md`
> **定位**：本文件是通用 AI 游戏工程治理体系的【工程技术基准】。它与 `AI_COLLABORATION.md`（协作协议内核）共同构成双轨治理基础。
> **通用性**：本文档不包含任何特定项目的实体名称、命名空间、玩法模块或文件路径。所有项目特化约束由外部【项目语义包】（`PROJECT_SEMANTIC_REGISTRY.md`、`PROJECT_DEPENDENCY_MATRIX.md`、`PROJECT_FAILURE_MEMORY.md`）注入。
> **配套协议**：`AI_COLLABORATION.md` V1.0+。本文件中的规则优先级、作用域标签与协作协议的仲裁系统完全咬合。

---

## 一、治理分层与文件边界

| 层级 | 职责 | 载体 |
|------|------|------|
| L1 协议层 | 档位、自升级、熵控制、状态机、扩展加载 | `AI_COLLABORATION.md` |
| **L2 工程标准层** | 编译红线、性能分级、运行时生命周期、影响半径流程、验证契约 | **本文件** |
| L3 项目语义层 | Critical Entity、禁止依赖、T1 热路径、已知失败模式 | `PROJECT_SEMANTIC_REGISTRY.md` 等外部文件 |
| L4 Runtime 治理层 | 风险快照维护、认知预算、状态回跳 | `AI_COLLABORATION.md` 运行时机制 |

**关键约束**：  
- 本文件中的规则若需要判定“是否为 Critical Entity”或“是否为 Forbidden Dependency”，必须**联动读取项目语义包**中的对应注册表。  
- 本文件不重复定义任何项目特化的危险实体清单、依赖矩阵或失败案例。

---

## 二、规则锚点与作用域系统（全局约定）

### 2.1 规则锚点 ID 格式

每条规则拥有唯一锚点 ID，由领域代码、类别代码和序号三部分组成，中间以短横线连接。

**格式**：领域代码-类别代码-序号

**领域代码对照表**：
- `C`：C# 编译与编码
- `ARCH`：架构治理
- `PERF`：性能治理
- `LIFECYCLE`：运行时生命周期
- `ASYNC`：异步治理
- `IMPACT`：影响半径治理
- `INPUT`：输入治理
- `DATA`：数据真理源
- `DEBUG`：调试治理
- `NATIVE`：C++ 原生插件
- `PYTHON`：Python 工具
- `TEST`：测试治理
- `LEGACY`：历史隔离
- `GIT`：版本控制

**示例**：`C-COMPILE-001`（编译零容忍）、`PERF-UPDATE-FIND-001`（Update 中禁止 Find）

### 2.2 规则作用域标签

每条规则附加作用域标签，定义其适用的代码域。AI 在执行时根据当前任务的文件路径和目的自动匹配作用域。

| 作用域标签 | 适用范围 | 典型宽松度 |
|-----------|---------|-----------|
| `SCOPE-ALL` | 所有代码域 | P0 基础安全规则，不可豁免 |
| `SCOPE-RUNTIME` | 游戏运行时逻辑 | 性能敏感，严格禁止 GC Alloc、Find 等 |
| `SCOPE-EDITOR` | Editor 工具、Inspector 扩展 | 允许 `AssetDatabase`、反射、`FindObjectOfType` |
| `SCOPE-DEBUG` | 调试代码（`#if DEBUG` 包裹） | 允许非最优写法，但需隔离 |
| `SCOPE-TEST` | 单元/集成测试 | 允许 Mock、反射注入 |
| `SCOPE-MIGRATION` | 一次性数据迁移脚本 | 允许临时 LINQ、批量扫描 |
| `SCOPE-PROTO` | 原型验证代码 | 除 `SCOPE-ALL` 规则外，其余降级为建议 |

AI 在任务启动时根据文件路径和任务描述自动判定作用域。跨作用域任务按最严格域执行，但需在产出清单中标注各文件所属作用域。

---

## 三、C# 编译与编码准入标准

| 锚点 ID | 规则内容 | 优先级 | 作用域 |
|---------|---------|--------|--------|
| `C-COMPILE-001` | Unity Console 必须 **0 Error** | P0 | `SCOPE-ALL` |
| `C-WARNING-001` | 非全局抑制警告必须 **0 Warning** | P1 | `SCOPE-ALL` |
| `C-NAMESPACE-001` | 使用项目统一命名空间（由项目语义包定义），禁止全局命名空间 | P2 | `SCOPE-RUNTIME` |
| `C-SINGLETON-001` | 单例使用 `Instance` + `Awake`，禁用 `FindObjectOfType` 查找单例 | P2 | `SCOPE-RUNTIME` |
| `C-FIND-001` | 禁止在运行时（Update/FixedUpdate/LateUpdate/协程/回调）使用 `GameObject.Find` / `FindObjectOfType` | P0 | `SCOPE-RUNTIME` |
| `C-EVENT-ONENABLE-001` | 事件订阅必须在 `OnEnable` 注册、`OnDisable` 注销，成对出现 | P0 | `SCOPE-ALL` |
| `C-SERIALIZE-001` | 存档数据结构必须标记 `[System.Serializable]`，禁止存储 `GameObject`、`Transform`、`MonoBehaviour` 等运行时引用 | P1 | `SCOPE-RUNTIME` |
| `C-COMMENT-001` | 公共 API 必须 `/// summary`，复杂算法需行内注释 | P4 | `SCOPE-ALL` |
| `C-DEFENSE-001` | 所有 `GetComponent` 返回后必须判空并 `Debug.LogError` | P0 | `SCOPE-ALL` |

---

## 四、架构治理（通用部分）

### 4.1 模块边界硬围栏

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `ARCH-INTERMODULE-001` | 项目语义包中定义的禁止依赖对之间，**严禁直接 `using` 引用**。唯一通信方式由语义包指定（如事件通道） | P2 | `SCOPE-RUNTIME` |
| `ARCH-UI-001` | 业务层（核心玩法/逻辑模块）禁止直接调用 UI 方法、修改 UI 状态或持有 UI 引用。UI 只能监听事件、展示数据、发送输入请求 | P2 | `SCOPE-RUNTIME` |

**具体禁止依赖矩阵**：由项目语义包 `PROJECT_DEPENDENCY_MATRIX.md` 维护。AI 在 RISK_SCAN 状态联动读取。

### 4.2 依赖扩散监控

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `ARCH-DEPEXPANSION-001` | 单任务中新增跨模块 `using` ≥ 3 时，触发 [Dependency Expansion Warning]，AI 须在产出清单中报告所有新增依赖 | P2 | `SCOPE-RUNTIME` |
| `ARCH-BIDIRECTIONAL-001` | 禁止出现双向依赖（A→B 且 B→A）。若发生，必须通过事件解耦 | P2 | `SCOPE-RUNTIME` |

### 4.3 Manager/Service 泛滥控制

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `ARCH-MANAGERDRIFT-001` | 非基础服务类（Manager/Service/Handler/Controller）新增数量 > 3 且跨 ≥3 个命名空间，且无统一接口或架构说明时，触发 [Drift Warning] | P2 | `SCOPE-RUNTIME` |

### 4.4 临时补丁量化限制

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `ARCH-WORKAROUND-001` | 单文件内 `// TODO: remove` / `#if WORKAROUND` / `if (legacyMode)` 等临时分支 ≥ 2 处，触发 [Entropy Warning] | P2 | `SCOPE-RUNTIME` |

---

## 五、性能治理

### 5.1 性能等级定义

| 级别 | 适用范围 | 核心约束 | 优先级 | 作用域 |
|------|---------|---------|--------|--------|
| P0 阻断 | `Update` / `FixedUpdate` / `LateUpdate` | 绝对禁止 GC Alloc，禁止 Find、无缓存 GetComponent、LINQ、字符串循环拼接 | P0 | `SCOPE-RUNTIME` |
| P1 审查 | 高频协程 / 每帧回调 / `Addressables.Completed` | 必须缓存引用，合理降低分配 | P1 | `SCOPE-RUNTIME` |
| P2 建议 | `Awake` / `Start` / 低频 UI 刷新（>1 秒间隔） | 允许非最优写法 | P2 | `SCOPE-RUNTIME` |

### 5.2 P0 绝对禁止项

以下行为在 P0 适用范围内无条件禁止：

| 锚点 ID | 禁止行为 | 说明 |
|---------|---------|------|
| `PERF-UPDATE-FIND-001` | `GameObject.Find` / `FindObjectOfType` | 无条件禁止 |
| `PERF-UPDATE-GETCOMP-001` | 无缓存 `GetComponent` 调用 | 必须提前在 Awake 中缓存 |
| `PERF-UPDATE-LINQ-001` | LINQ（`Where`/`Select`/`ToList` 等） | 产生 GC Alloc |
| `PERF-UPDATE-FOREACH-001` | `foreach` 遍历值类型集合（装箱） | 使用 `for` 替代 |
| `PERF-UPDATE-STRING-001` | 循环内字符串拼接 `+` | 使用 `StringBuilder` |
| `PERF-UPDATE-LAYOUT-001` | `LayoutRebuilder` 高频强制重建 | 禁止逐帧调用 |

### 5.3 高频缓存强制项

以下对象在 P1 及以上性能路径中必须提前缓存：

| 锚点 ID | 必须缓存对象 |
|---------|-------------|
| `PERF-CACHE-TRANSFORM-001` | `Transform` |
| `PERF-CACHE-ANIMATOR-001` | `Animator` |
| `PERF-CACHE-CAMERA-001` | `Camera` |
| `PERF-CACHE-RIGIDBODY-001` | `Rigidbody` |
| `PERF-CACHE-SHADERID-001` | `Shader.PropertyToID` 结果 |

### 5.4 项目特化性能约束

项目语义包中标记为 [HIGH_FREQUENCY] 的核心组件，必须遵守以下通用规则：

| 锚点 ID | 约束 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `PERF-HIGHFREQ-CACHE-001` | 所有访问必须提前缓存引用 | P0 | `SCOPE-RUNTIME` |
| `PERF-HIGHFREQ-BOUNDARY-001` | 访问集合/数组时必须检查索引合法性 | P0 | `SCOPE-RUNTIME` |
| `PERF-HIGHFREQ-NULL-001` | 访问可能为空的引用时必须判空 | P0 | `SCOPE-RUNTIME` |

（具体哪些组件属于 [HIGH_FREQUENCY] 由项目语义包定义。）

---

## 六、运行时生命周期治理

### 6.1 统一生命周期闭环

所有分配型资源必须遵循“创建 → 使用 → 释放”闭环：

| 锚点 ID | 资源类型 | 释放方法 | 优先级 | 作用域 |
|---------|---------|---------|--------|--------|
| `LIFECYCLE-ADDRESSABLES-001` | Addressables Handle | `Addressables.Release(handle)` | P1 | `SCOPE-RUNTIME` |
| `LIFECYCLE-MATERIAL-001` | 运行时创建的 Material 实例 | `Destroy(materialInstance)` | P1 | `SCOPE-RUNTIME` |
| `LIFECYCLE-NATIVEARRAY-001` | NativeArray / NativeList | `Dispose()` | P1 | `SCOPE-RUNTIME` |
| `LIFECYCLE-COMPUTEBUFFER-001` | ComputeBuffer | `Dispose()` / `Release()` | P1 | `SCOPE-RUNTIME` |
| `LIFECYCLE-COROUTINE-001` | Coroutine | `StopCoroutine()` 在 OnDisable | P1 | `SCOPE-RUNTIME` |

### 6.2 Addressables 专项治理

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `LIFECYCLE-ADDR-RELEASE-001` | 禁止 LoadAssetAsync 后不 Release；禁止场景卸载后持有 Handle | P1 | `SCOPE-RUNTIME` |
| `LIFECYCLE-ADDR-CALLBACK-001` | Completed 回调中必须检查 `this != null` 和对象有效性 | P1 | `SCOPE-RUNTIME` |

### 6.3 状态污染治理

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `LIFECYCLE-STATE-PERSISTENT-001` | `static` 字段、DontDestroyOnLoad 单例、手动 Runtime Cache 视为 Persistent Runtime State | P1 | `SCOPE-RUNTIME` |
| `LIFECYCLE-STATE-SCENE-001` | 修改 Persistent Runtime State 时必须验证：场景重载后无无效引用、存档前后状态一致、无重复实例 | P1 | `SCOPE-RUNTIME` |
| `LIFECYCLE-STATE-CACHE-001` | 禁止静态缓存场景对象引用；禁止单例持有已销毁对象；禁止 DontDestroyOnLoad 重复生成 | P0 | `SCOPE-RUNTIME` |

---

## 七、异步运行时治理

### 7.1 异步边界认定

以下视为异步边界：Coroutine、async/await（UniTask）、Addressables、UnityWebRequest、Native Callback。

### 7.2 异步禁止项

| 锚点 ID | 禁止行为 | 优先级 | 作用域 |
|---------|---------|--------|--------|
| `ASYNC-VOID-001` | `async void` 用于业务逻辑（仅允许事件处理器） | P1 | `SCOPE-RUNTIME` |
| `ASYNC-THREAD-001` | 跨线程直接调用 Unity API（须回主线程） | P0 | `SCOPE-ALL` |
| `ASYNC-INFINITE-001` | 无退出条件的无限循环协程 | P1 | `SCOPE-RUNTIME` |
| `ASYNC-DESTROYED-001` | 对象销毁后仍执行回调（未检查有效性） | P0 | `SCOPE-RUNTIME` |
| `ASYNC-HANDLELEAK-001` | Handle 分配后不释放 | P1 | `SCOPE-RUNTIME` |

### 7.3 异步生命周期检查清单

AI 在 VERIFYING 状态对每个异步边界必须检查：

| 锚点 ID | 检查项 | 优先级 |
|---------|--------|--------|
| `ASYNC-CHECK-THIS-001` | 回调中检查 `this != null` 和对象激活状态 | P1 |
| `ASYNC-CHECK-TOKEN-001` | 正确传递 CancellationToken（若使用） | P1 |
| `ASYNC-CHECK-STOP-001` | StopCoroutine 在 OnDisable 中执行 | P1 |
| `ASYNC-CHECK-RELEASE-001` | Handle.Release() 在 OnDestroy 中执行 | P1 |

---

## 八、影响半径治理（通用流程）

**激活条件**：当修改触及项目语义包中标记为 `ENT-CRIT-*` 或 `ENT-T1-*` 的实体时，本规则激活。

### 8.1 通用影响半径检查流程

AI 在修改 Critical Entity 后，必须按以下通用流程执行检查：

1. **边界与空值验证**：索引操作是否检查了边界？引用访问是否判空？
2. **关联系统同步**：项目语义包中定义的关联系统是否需要同步修改？
3. **序列化兼容**（若涉及数据持久化）：新增字段是否提供默认值？旧数据是否兼容？
4. **事件/回调闭环**：新增订阅是否成对注销？Payload 结构是否可序列化？
5. **UI 联动**：是否影响 UI 层？UI 监听器是否需要同步调整？
6. **场景/生命周期安全**：场景加载/卸载后状态是否一致？资源是否正确释放？

具体实体的关联系统映射、具体验证步骤的优先级，由项目语义包 `PROJECT_SEMANTIC_REGISTRY.md` 中的 Impact Radius Mapping 表提供。

---

## 九、输入治理

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `INPUT-ROUTE-001` | 禁止多个系统消费同一输入。输入路由由统一的 InputRouter 或 InputAction 管理 | P2 | `SCOPE-RUNTIME` |
| `INPUT-UI-LOCK-001` | UI 打开时必须锁定 Gameplay 输入 | P2 | `SCOPE-RUNTIME` |
| `INPUT-KEYCODE-001` | 禁止在 Update 中硬编码 KeyCode 常量 | P2 | `SCOPE-RUNTIME` |

---

## 十、数据真理源治理

| 锚点 ID | 数据类型 | 真理源（Single Source of Truth） | 优先级 |
|---------|---------|--------------------------------|--------|
| `DATA-SO-001` | 静态配置 | ScriptableObject | P2 |
| `DATA-CSV-001` | 数值/表格配置 | DataTables CSV | P2 |
| `DATA-SAVE-001` | Runtime 持久化状态 | 存档系统数据结构 | P1 |
| `DATA-VIEWMODEL-001` | UI 展示数据 | ViewModel（从事件/状态派生） | P2 |

**禁止项**：

| 锚点 ID | 禁止行为 | 优先级 |
|---------|---------|--------|
| `DATA-UI-NOBIZ-001` | UI 直接保存业务状态 | P2 |
| `DATA-SO-NORUNTIME-001` | ScriptableObject 存储运行时可变数据 | P2 |
| `DATA-MULTIWRITE-001` | 多个系统不经协调直接修改同一 Runtime 状态 | P2 |

---

## 十一、Debug 治理

| 锚点 ID | 规则 | 优先级 | 作用域 |
|---------|------|--------|--------|
| `DEBUG-LOCATION-001` | 调试代码放入项目约定的 Debug 目录 | P3 | `SCOPE-ALL` |
| `DEBUG-IFDEF-001` | 使用 `#if DEBUG` 包裹，禁止污染 Release 构建 | P3 | `SCOPE-ALL` |
| `DEBUG-NOECON-001` | 禁止 Debug 面板修改正式经济/业务数据 | P2 | `SCOPE-ALL` |
| `DEBUG-NOHOOK-001` | 禁止 Debug Hook 永久保留在生产代码中 | P2 | `SCOPE-ALL` |

---

## 十二、C++ Native Plugin 治理（通用）

| 锚点 ID | 规则 | 优先级 |
|---------|------|--------|
| `NATIVE-EXTERN-001` | 导出函数必须 `extern "C"`，签名稳定 | P2 |
| `NATIVE-STRING-001` | 返回字符串由调用方管理内存，C# 端正确释放 | P1 |
| `NATIVE-INTPTR-001` | 禁止长期持有 IntPtr 不管理生命周期 | P1 |
| `NATIVE-THREAD-001` | 非主线程回调禁止直接调用 Unity API，须派发回主线程 | P0 |

---

## 十三、Python 工具治理（通用）

| 锚点 ID | 规则 | 优先级 |
|---------|------|--------|
| `PYTHON-VERSION-001` | 使用项目约定的 Python 版本，遵循 PEP8 | P2 |
| `PYTHON-BOUNDARY-001` | 与 Unity 交互仅限序列化边界（CSV、JSON、ScriptableObject 生成），禁止反射调用 Unity Runtime | P2 |
| `PYTHON-TRYEXCEPT-001` | 所有入口点包裹 try-except，异常记入日志 | P1 |

---

## 十四、验证契约

### 14.1 最低验证标准

AI 在 VERIFYING 状态，修改涉及以下通用类型时，必须提供对应验证方式。禁止以“理论上应该没问题”作为结论。

| 锚点 ID | 修改类型 | 最低验证要求 | 优先级 |
|---------|---------|-------------|--------|
| `VERIFY-DATA-ROUNDTRIP-001` | 持久化数据结构字段变更 | 序列化/反序列化往返测试，校验字段完整性 | P1 |
| `VERIFY-EVENT-SUBUNSUB-001` | 事件系统签名变更 | 验证订阅/注销成对，无残留回调 | P1 |
| `VERIFY-CORE-INDEX-001` | 核心数组/集合索引操作 | 边界测试（空、满、越界） | P0 |
| `VERIFY-FORMULA-001` | 核心计算公式修改 | 覆盖所有分支（含边界值）的数值验证 | P1 |
| `VERIFY-TIME-ADVANCE-001` | 核心时间/状态推进 | 多周期推进后验证所有关联系统状态一致 | P1 |
| `VERIFY-UI-RUNTIME-001` | UI 交互逻辑 | 运行时交互测试（面板开关、事件响应） | P2 |
| `VERIFY-SCENE-RELOAD-001` | 场景加载/卸载 | 重载后检查静态残留、单例重复、资源泄漏 | P2 |

### 14.2 验证层级定义

| 锚点 ID | 验证层级 | 说明 | 优先级 |
|---------|---------|------|--------|
| `VERIFY-LEVEL-COMPILE-001` | Compile Verification | 0 Error | P0 |
| `VERIFY-LEVEL-RUNTIME-001` | Runtime Verification | 至少一次 Play Mode 运行，关键路径无异常 | P1 |
| `VERIFY-LEVEL-STATE-001` | State Verification | 涉及存档、全局状态、场景切换时，状态前后一致 | P1 |
| `VERIFY-LEVEL-LIFECYCLE-001` | Lifecycle Verification | 涉及资源分配时，确保正确释放 | P1 |

**强制规则**：涉及数据持久化、事件系统、场景切换时，**禁止仅进行 Compile Verification**，必须包含 Runtime/State Verification。

| 锚点 ID | 规则 | 优先级 |
|---------|------|--------|
| `VERIFY-FORCE-RUNTIME-001` | 修改触及项目语义包中 `ENT-CRIT-*` 实体时，禁止仅以编译通过作为验证结论 | P1 |

---

## 十五、测试治理

| 锚点 ID | 级别 | 范围 | 要求 | 优先级 |
|---------|------|------|------|--------|
| `TEST-T3-001` | T3 强制 | 项目语义包定义的核心系统 | EditMode 测试或明确测试脚本，覆盖分支/边界/空状态 | P1 |
| `TEST-T2-001` | T2 场景 | 常规业务模块 | PlayMode 测试或手动测试步骤清单 | P2 |
| `TEST-T1-001` | T1 降级 | UI 动画、音效等 | Runtime Assertion 可替代，需简述验证方式 | P3 |

---

## 十六、历史污染隔离

| 锚点 ID | 规则 | 优先级 |
|---------|------|--------|
| `LEGACY-QUARANTINE-001` | 项目约定的废弃代码目录默认禁止 AI 主动参考 | P3 |
| `LEGACY-RETIRE-001` | 废弃模块退役时须在约定位置记录：废弃原因、替代模块、风险说明 | P3 |

---

## 十七、Git 治理

| 锚点 ID | 规则 | 优先级 |
|---------|------|--------|
| `GIT-FORMAT-001` | 提交信息格式：`feat(scope):` / `fix(scope):` / `refactor(scope):` / `docs:` | P4 |
| `GIT-NOAUTO-001` | AI 可建议提交命令，但不得自动执行 Git 操作 | P4 |

---

## 十八、与协作协议及项目语义包的咬合

| 本文件不定义 | 由外部载体维护 | 引用方式 |
|-------------|---------------|---------|
| Critical Entity 清单 | `PROJECT_SEMANTIC_REGISTRY.md` | 第八节影响半径检查触发时联动读取 |
| Forbidden Dependency 矩阵 | `PROJECT_DEPENDENCY_MATRIX.md` | 第四节架构治理联动读取 |
| T1 硬检查热路径 | `PROJECT_SEMANTIC_REGISTRY.md` | 防御性检查触发时联动读取 |
| 已知失败模式 | `PROJECT_FAILURE_MEMORY.md` | AI 在 RISK_SCAN 状态联动读取 |
| 具体模块的 Impact Radius 映射 | `PROJECT_SEMANTIC_REGISTRY.md` | 第八节影响半径检查流程参照 |
| 自升级触发条件 | `AI_COLLABORATION.md` | 本文件不涉及 |
| 熵增检测阈值 | `AI_COLLABORATION.md` | 本文件仅定义局部补丁阈值 |

---

> **本文件为通用工程技术基准 V1.0。与 `AI_COLLABORATION.md` V1.0+ 及项目语义包共同构成完整的 AI 游戏工程治理体系。**