PROFILE_FIELDS = [
    {
        "id": "businessModel",
        "label": "商业模式",
        "options": [
            ("unknown", "未确定"),
            ("buyout", "买断制"),
            ("free_to_play", "免费游玩"),
            ("subscription", "订阅制"),
            ("premium_with_dlc", "买断制 + DLC"),
        ],
    },
    {
        "id": "operationModel",
        "label": "运营模式",
        "options": [
            ("unknown", "未确定"),
            ("offline_single_release", "离线单次发布"),
            ("content_updates", "持续内容更新"),
            ("live_service", "长线服务运营"),
        ],
    },
    {
        "id": "socialModel",
        "label": "社交结构",
        "options": [
            ("unknown", "未确定"),
            ("none", "无社交"),
            ("async_light", "轻量异步社交"),
            ("multiplayer", "多人在线"),
            ("community_driven", "社区驱动"),
        ],
    },
    {
        "id": "platformScope",
        "label": "平台范围",
        "options": [
            ("unknown", "未确定"),
            ("single_platform", "单平台"),
            ("multi_platform", "多平台"),
        ],
    },
    {
        "id": "primaryPlatform",
        "label": "主平台",
        "options": [
            ("unknown", "未确定"),
            ("mobile", "手机"),
            ("pc_console", "PC / 主机"),
            ("web", "Web"),
            ("cross_platform", "跨平台同等优先"),
        ],
    },
    {
        "id": "regionScope",
        "label": "发行区域",
        "options": [
            ("unknown", "未确定"),
            ("single_region", "单一区域"),
            ("multi_region", "多区域"),
            ("global", "全球发行"),
        ],
    },
    {
        "id": "targetScale",
        "label": "项目规模",
        "options": [
            ("unknown", "未确定"),
            ("iaa_hypercasual", "IAA 超休闲小游戏"),
            ("indie", "独立游戏"),
            ("midcore", "中度商业游戏"),
            ("3a", "3A 游戏"),
            ("large_service", "大型长线服务游戏"),
        ],
    },
    {
        "id": "contentRating",
        "label": "内容分级",
        "options": [
            ("unknown", "未确定"),
            ("all_ages", "全年龄"),
            ("teen", "青少年"),
            ("mature_17_plus", "M / 17+"),
        ],
    },
    {
        "id": "targetSessionBand",
        "label": "目标单次时长",
        "options": [
            ("unknown", "未确定"),
            ("session_1_3", "1-3 分钟"),
            ("session_3_10", "3-10 分钟"),
            ("session_10_20", "10-20 分钟"),
            ("session_20_40", "20-40 分钟"),
            ("session_40_plus", "40 分钟以上"),
        ],
    },
]


PROFILE_DEFAULTS = {field["id"]: "unknown" for field in PROFILE_FIELDS}
PROFILE_FIELD_LABELS = {field["id"]: field["label"] for field in PROFILE_FIELDS}
PROFILE_OPTION_LABELS = {
    field["id"]: {value: label for value, label in field["options"]}
    for field in PROFILE_FIELDS
}
PROFILE_VALUE_BY_LABEL = {
    field["id"]: {label: value for value, label in field["options"]}
    for field in PROFILE_FIELDS
}


def field_label(field_id):
    return PROFILE_FIELD_LABELS.get(field_id, field_id)


def option_label(field_id, value):
    return PROFILE_OPTION_LABELS.get(field_id, {}).get(value, value)


def value_from_label(field_id, label):
    return PROFILE_VALUE_BY_LABEL.get(field_id, {}).get(label, label)


def display_profile(profile):
    return {
        field_label(field_id): option_label(field_id, value)
        for field_id, value in profile.items()
    }
