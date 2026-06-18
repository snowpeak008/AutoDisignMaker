# API Config

```yaml
# ==============================
# API 统一配置
# api_config.yaml 请加入 .gitignore，永不提交
# ==============================

providers:
  # ═══════════════════════════════════════
  # 当前激活 ── 中转代理（OpenAI 兼容 Chat Completions）
  # ═══════════════════════════════════════
  llm:
    provider: "openai"
    api_key: "sk-7aa6725e65f78d05cd87015c94274292877b0018ec62877f435c9dc148cc3192"
    base_url: "https://vip.auto-code.net/v1"
    default_model: "gpt-5.5"
    models:
      chat: "gpt-5.5"

  # ═══════════════════════════════════════
  # 备用中转代理（已停用）
  # ═══════════════════════════════════════
  # llm:
  #   provider: "openai"
  #   api_key: "sk-7dcab66d425f571a9873c01720f750b0f8fb7fc2d592d1f569864e18ace59e52"
  #   base_url: "https://vip.auto-code.net/v1"
  #   default_model: "gpt-5.5"
  #   models:
  #     chat: "gpt-5.5"

  # ═══════════════════════════════════════
  # 预设 1 ── 中转代理（OpenAI 兼容）
  # ═══════════════════════════════════════
  # llm:
  #   provider: "openai"
  #   api_key: "sk-xxx"
  #   base_url: "https://vip.auto-code.net/v1"
  #   default_model: "gpt-5.5"
  #   models:
  #     chat: "gpt-5.5"

  # ═══════════════════════════════════════
  # 预设 2 ── OpenAI 官方
  # ═══════════════════════════════════════
  # llm:
  #   provider: "openai"
  #   api_key: "sk-xxx"
  #   base_url: "https://api.openai.com/v1"
  #   default_model: "gpt-4o"
  #   models:
  #     chat: "gpt-4o"

  # ═══════════════════════════════════════
  # 预设 3 ── Anthropic Claude
  # ═══════════════════════════════════════
  # llm:
  #   provider: "anthropic"
  #   api_key: "sk-ant-xxx"
  #   base_url: "https://api.anthropic.com"
  #   default_model: "claude-sonnet-4-6"
  #   models:
  #     chat: "claude-sonnet-4-6"

  # ----- IMAGE2 (图片生成) -----
  image2:
    api_key: "sk-daba015a3be1b595faa8d7d3dc7f8741202b468bbc441400abba5cb953af6bfd"
    base_url: "https://vip.auto-code.net/v1"
    default_model: "gpt-image-2"

  # ----- IMAGE API ROUTING -----
  # active 只控制当前实际调用的平台；暂时只使用 relay。
  # relay 继承上面的 image2 配置，避免同一密钥复制多份。
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
  dev_work_dir: "E:/workwork/steamgamework/sea_water/sea_wwater"
  editor_path: "E:/workwork/steamgamework/unit/2022.3.62f3c1/Editor/Unity.exe"
  unity_targets:
    windows: "StandaloneWindows64"
    android: "Android"
    ios: "iOS"
    webgl: "WebGL"

localization:
  enabled: true
  default_language: "zh-CN"
  supported_languages: ["zh-CN", "en-US"]

```
