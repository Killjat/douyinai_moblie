"""
系统依赖检测接口
"""
import os
import subprocess
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

DEPS = {
    "adb":          ["adb", "version"],
    "agent-device": ["agent-device", "--version"],
    "node":         ["node", "--version"],
    "python3":      ["python3", "--version"],
}


def _check(cmd: list) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        ok = r.returncode == 0
        return {"ok": ok, "version": (r.stdout or r.stderr).strip().splitlines()[0] if ok else ""}
    except FileNotFoundError:
        return {"ok": False, "version": ""}
    except Exception as e:
        return {"ok": False, "version": str(e)}


def _check_adbkeyboard() -> dict:
    try:
        r = subprocess.run(["adb", "shell", "ime", "list", "-s"],
                           capture_output=True, text=True, timeout=5)
        installed = "com.android.adbkeyboard/.AdbIME" in r.stdout
        return {"ok": installed, "version": "AdbIME" if installed else ""}
    except Exception:
        return {"ok": False, "version": ""}


def _check_device() -> dict:
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = [l for l in r.stdout.strip().splitlines()[1:] if l.strip() and "device" in l]
        return {"ok": len(lines) > 0, "version": lines[0].split()[0] if lines else ""}
    except Exception:
        return {"ok": False, "version": ""}


@router.get("/deps")
def check_deps():
    result = {}
    for name, cmd in DEPS.items():
        result[name] = _check(cmd)
    result["adbkeyboard"] = _check_adbkeyboard()
    result["device"] = _check_device()
    return result


def _sse(msg: dict) -> str:
    return f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"


async def _install_all_stream():
    """依次安装所有缺失依赖，SSE 实时推送进度。"""
    import asyncio

    steps = [
        {
            "name": "Homebrew",
            "check": lambda: _check(["brew", "--version"])["ok"],
            "cmd": ["/bin/bash", "-c",
                    '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'],
            "desc": "安装 Homebrew（Mac 包管理器）",
        },
        {
            "name": "ADB",
            "check": lambda: _check(["adb", "version"])["ok"],
            "cmd": ["brew", "install", "android-platform-tools"],
            "desc": "安装 ADB（Android 调试工具）",
        },
        {
            "name": "Node.js",
            "check": lambda: _check(["node", "--version"])["ok"],
            "cmd": ["brew", "install", "node"],
            "desc": "安装 Node.js",
        },
        {
            "name": "agent-device",
            "check": lambda: _check(["agent-device", "--version"])["ok"],
            "cmd": ["npm", "install", "-g", "agent-device"],
            "desc": "安装 agent-device（设备控制工具）",
        },
        {
            "name": "ADBKeyboard",
            "check": lambda: _check_adbkeyboard()["ok"],
            "cmd": None,  # APK 安装单独处理
            "desc": "安装 ADBKeyboard（中文输入法）",
        },
    ]

    for step in steps:
        name = step["name"]
        if step["check"]():
            yield _sse({"step": name, "status": "skip", "msg": f"{name} 已安装，跳过"})
            continue

        yield _sse({"step": name, "status": "running", "msg": step["desc"]})

        if step["cmd"] is None:
            # ADBKeyboard APK 安装
            apk_path = os.path.join(os.path.dirname(__file__), "../../resources/ADBKeyboard.apk")
            if not os.path.exists(apk_path):
                yield _sse({"step": name, "status": "warn",
                            "msg": "ADBKeyboard.apk 未找到，请确保手机已连接后在系统检测页手动安装"})
                continue
            try:
                r = subprocess.run(["adb", "install", "-r", apk_path],
                                   capture_output=True, text=True, timeout=30)
                ok = "Success" in r.stdout
                yield _sse({"step": name, "status": "ok" if ok else "fail",
                            "msg": r.stdout.strip() or r.stderr.strip()})
            except Exception as e:
                yield _sse({"step": name, "status": "fail", "msg": str(e)})
            continue

        try:
            r = subprocess.run(step["cmd"], capture_output=True, text=True, timeout=120)
            ok = r.returncode == 0
            yield _sse({"step": name, "status": "ok" if ok else "fail",
                        "msg": (r.stdout or r.stderr).strip()[:200]})
        except Exception as e:
            yield _sse({"step": name, "status": "fail", "msg": str(e)})

    yield _sse({"step": "done", "status": "done", "msg": "所有依赖安装完成，请重新检测"})


@router.post("/install-all")
async def install_all():
    """一键安装所有缺失依赖，SSE 实时推送进度。"""
    return StreamingResponse(
        _install_all_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/install/{dep}")
def install_dep(dep: str):
    cmds = {"agent-device": ["npm", "install", "-g", "agent-device"]}
    if dep not in cmds:
        return {"ok": False, "msg": f"不支持自动安装: {dep}"}
    try:
        r = subprocess.run(cmds[dep], capture_output=True, text=True, timeout=60)
        return {"ok": r.returncode == 0, "msg": r.stdout or r.stderr}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.post("/install-apk")
def install_apk():
    apk_path = os.path.join(os.path.dirname(__file__), "../../resources/ADBKeyboard.apk")
    if not os.path.exists(apk_path):
        return {"ok": False, "msg": "APK 文件不存在"}
    try:
        r = subprocess.run(["adb", "install", "-r", apk_path],
                           capture_output=True, text=True, timeout=30)
        return {"ok": "Success" in r.stdout, "msg": r.stdout or r.stderr}
    except Exception as e:
        return {"ok": False, "msg": str(e)}
