# API 统一配置模板

使用说明：
1. 复制此文件为 `api_config.md`
2. 按需保留/添加 provider（服务商）
3. `api_config.md` 请加入 `.gitignore`，永不提交

```yaml
# ── 每个 provider 的最小必填字段 ──
#   provider:        # 服务商名称（自定义，脚本中通过此名引用）
#     api_key: ""      # API 密钥（支持直接填写或留空从环境变量读取）
#     base_url: ""     # API 基础地址（必填）
#     default_model: ""# 默认模型名
#     models: {}       # 可选：额外模型别名（key=别名, value=实际模型名）

providers:

  # ----- 默认 LLM：OpenAI 兼容中转代理 -----
  llm:
    provider: "openai"
    api_key: ""                            # 留空则自动从环境变量 LLM_API_KEY 读取
    base_url: "https://vip.auto-code.net/v1"
    default_model: "gpt-5.5"
    models:
      chat: "gpt-5.5"

  # ----- DeepSeek -----
  deepseek:
    provider: "deepseek"
    api_key: ""                           # 若留空则自动从环境变量 DEEPSEEK_API_KEY 读取
    base_url: "https://api.deepseek.com"
    default_model: "deepseek-chat"
    models:
      chat: "deepseek-chat"
      flash: "deepseek-v4-flash"         # 如果使用 V4 Flash

  # ----- OpenAI (或任何 OpenAI 兼容中转) -----
  openai:
    provider: "openai"
    api_key: ""
    base_url: "https://api.openai.com/v1"   # 若用中转，改为中转地址
    default_model: "gpt-4o"
    models:
      default: "gpt-4o"
      mini: "gpt-4o-mini"

  # ----- 自定义中转示例 (如 one-api, aihubmix 等) -----
  # my_proxy:
  #   api_key: ""
  #   base_url: "https://your-proxy.com/v1"
  #   default_model: "gpt-4o"
  #   models:
  #     thinking: "claude-3-5-sonnet"
  #     cheap: "gpt-3.5-turbo"

  # ----- IMAGE2 (图片生成专用) -----
  image2:
    api_key: ""                           # 留空则从 IMAGE2_API_KEY 环境变量读取
    base_url: "https://vip.auto-code.net/v1"
    default_model: "gpt-image-2"
    # models 非必须

  # ----- IMAGE API ROUTING -----
  # active controls the provider used by image_api_probe.py and future art generation.
  # Keep real keys in api_config.md or environment variables; do not commit them.
  image_apis:
    active: "relay"
    relay:
      provider: "openai_responses"
      mode: "responses_image_tool"
      inherit_from: "image2"
      endpoint: "responses"
      response_model: "gpt-5.5"
      image_model: "gpt-image-2"
      enabled: true
    openai:
      provider: "openai"
      mode: "images_generations"
      api_key_env: "OPENAI_IMAGE_API_KEY"
      base_url: "https://api.openai.com/v1"
      endpoint: "images/generations"
      image_model: "gpt-image-1"
      enabled: false
    banana:
      provider: "banana"
      mode: "images_generations"
      api_key_env: "BANANA_IMAGE_API_KEY"
      base_url: "https://api.banana.dev/v1"
      endpoint: "images/generations"
      image_model: "banana-image"
      enabled: false

project:
  dev_work_dir: "D:/YourGame/Project"
  editor_path: "C:/Program Files/Unity/Hub/Editor/6000.0.34f1/Editor/Unity.exe"
  unity_targets:
    windows: "StandaloneWindows64"
    android: "Android"
    ios: "iOS"
    webgl: "WebGL"

localization:
  enabled: true
  default_language: "zh-CN"
  supported_languages: ["zh-CN", "en-US", "ja-JP"]
```
