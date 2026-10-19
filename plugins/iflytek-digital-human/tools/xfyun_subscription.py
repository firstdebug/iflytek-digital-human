#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create IFLYTEK digital-human subscription orders.

The endpoint accepts two product families:
  appType=1: interface product for SDK/WebAPI projects.
  appType=2: standard product for Web templates/PC assistant/live products.

The platform currently accepts these orders without a captcha. The returned
status is reported as-is; the client never treats a standard-product order as
approved because it still requires operations review.
"""

import argparse
import copy
import json
import sys

import xfyun_common as xc


API_ORDER_UPSERT = "https://virtual-man.xfyun.cn/zs_web/order/createOrUpdate"

_LLM_DEFAULT = {
    "llmTokensNum": 1,
    "llmDialogNum": 500000,
    "llmDocNum": 100,
}

DEFAULT_ORDERS = {
    1: {
        "appType": 1,
        "orderType": 2,
        "appName": "123",
        "appDesc": "123",
        "company": "123",
        "contact": "",
        "phone": "",
        "effectTime": 2592000000,
        "avatarInteraction": {
            "avatarInteractionConcNum": 1,
            "avatarInteractionTime": 12000000,
        },
        "llmConversation": copy.deepcopy(_LLM_DEFAULT),
        "sceneNum": 3,
    },
    2: {
        "appType": 2,
        "orderType": 2,
        "appName": "应用申请",
        "appDesc": "应用申请123",
        "company": "应用申请",
        "contact": "",
        "phone": "",
        "effectTime": 604800000,
        "avatarInteraction": {"avatarInteractionConcNum": 1},
        "llmConversation": copy.deepcopy(_LLM_DEFAULT),
        "productType": ["WEB_CONVERSATION", "PC_ASSISTANT", "DIGITAL_LIVE"],
        "sceneNum": 3,
    },
}

REVIEW_POLICIES = {
    1: "auto_review",
    2: "operations_review",
}


def build_order_payload(app_type, overrides=None):
    """Build a fresh platform payload without adding captcha fields."""
    try:
        app_type = int(app_type)
    except (TypeError, ValueError):
        raise ValueError("appType must be 1 or 2")
    if app_type not in DEFAULT_ORDERS:
        raise ValueError("appType must be 1 or 2")

    payload = copy.deepcopy(DEFAULT_ORDERS[app_type])
    for key, value in (overrides or {}).items():
        if key in ("avatarInteraction", "llmConversation"):
            if not isinstance(value, dict):
                raise ValueError("{} must be an object".format(key))
            payload[key].update(value)
        elif value is not None:
            payload[key] = value
    payload["appType"] = app_type
    return payload


def _is_success(response):
    if not isinstance(response, dict):
        return False
    return (response.get("flag") is True
            or response.get("retcode") == 200
            or response.get("code") in (0, "0", 200, "200"))


def _first_value(value, keys):
    if isinstance(value, dict):
        for key in keys:
            if value.get(key) not in (None, ""):
                return value[key]
        for child in value.values():
            found = _first_value(child, keys)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_value(child, keys)
            if found not in (None, ""):
                return found
    return None


def submit_order(session, app_type, overrides=None, debug=False):
    """Submit an order and return a stable, non-sensitive result object."""
    payload = build_order_payload(app_type, overrides)
    response = xc.post(session, API_ORDER_UPSERT, payload, debug=debug)
    if not _is_success(response):
        return {
            "ok": False,
            "appType": payload["appType"],
            "review": REVIEW_POLICIES[payload["appType"]],
            "response": response,
        }
    return {
        "ok": True,
        "appType": payload["appType"],
        "review": REVIEW_POLICIES[payload["appType"]],
        "orderId": _first_value(response, ("orderId", "id")),
        "status": _first_value(response, ("status", "orderStatus", "auditStatus")),
        "response": response,
    }


def _parser():
    parser = argparse.ArgumentParser(description="创建讯飞虚拟人订阅申请")
    parser.add_argument("app_type", type=int, choices=(1, 2),
                        help="1=接口产品(SDK/WebAPI)，2=标准产品(Web模板/直播)")
    parser.add_argument("--app-name")
    parser.add_argument("--app-desc")
    parser.add_argument("--company")
    parser.add_argument("--contact")
    parser.add_argument("--phone")
    parser.add_argument("--effect-time", type=int)
    parser.add_argument("--scene-num", type=int)
    parser.add_argument("--avatar-concurrency", type=int)
    parser.add_argument("--avatar-time", type=int)
    parser.add_argument("--product-type", action="append",
                        choices=("WEB_CONVERSATION", "PC_ASSISTANT", "DIGITAL_LIVE"),
                        help="标准产品能力，可重复传入")
    parser.add_argument("--dry-run", action="store_true", help="只打印脱敏前的请求结构，不提交")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    key_map = {
        "app_name": "appName",
        "app_desc": "appDesc",
        "effect_time": "effectTime",
        "scene_num": "sceneNum",
    }
    overrides = {
        key_map.get(key, key): getattr(args, key)
        for key in ("app_name", "app_desc", "company", "contact", "phone", "effect_time", "scene_num")
        if getattr(args, key) is not None
    }
    if args.avatar_concurrency is not None or args.avatar_time is not None:
        overrides["avatarInteraction"] = {}
        if args.avatar_concurrency is not None:
            overrides["avatarInteraction"]["avatarInteractionConcNum"] = args.avatar_concurrency
        if args.avatar_time is not None:
            overrides["avatarInteraction"]["avatarInteractionTime"] = args.avatar_time
    if args.product_type:
        overrides["productType"] = args.product_type

    payload = build_order_payload(args.app_type, overrides)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    session = xc.get_session()
    if not session:
        print("[失败] 未取得登录会话")
        return 1
    result = submit_order(session, args.app_type, overrides)
    if not result["ok"]:
        print("[失败] 订阅申请提交失败")
        return 1

    if args.app_type == 1:
        print("[OK] 接口产品订阅申请已提交，平台将自动审核。")
    else:
        print("[OK] 标准产品订阅申请已提交，仍需等待运营审核。")
        print("      Web 模板/数字人产品审核通过后才能继续创建场景。")
    if result.get("orderId"):
        print("  orderId: {}".format(result["orderId"]))
    if result.get("status"):
        print("  平台状态: {}".format(result["status"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
