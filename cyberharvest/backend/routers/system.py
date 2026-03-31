"""
系统依赖检测接口
"""
import subprocess
from fastapi import APIRouter

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


@router.get("/deps")
def check_deps():
    """检测所有依赖是否已安装"""
    result = {}
    for name, cmd in DEPS.items():
        result[name] = _check(cmd)

    # 检测 ADBKeyboard
    try:
        r = subprocess.run(
            ["adb", "shell", "ime", "list", "-s"],
            capture_output=True, text=True, timeout=5
        )
        installed = "com.android.adbkeyboard/.AdbIME" in r.stdout
        result["adbkeyboard"] = {"ok": installed, "version": "AdbIME" if installed else ""}
    except Exception:
        result["adbkeyboard"] = {"ok": False, "version": ""}

    # 检测设备连接
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = [l for l in r.stdout.strip().splitlines()[1:] if l.strip() and "device" in l]
        result["device"] = {"ok": len(lines) > 0, "version": lines[0].split()[0] if lines else ""}
    except Exception:
        result["device"] = {"ok": False, "version": ""}

    return result


@router.post("/install/{dep}")
def install_dep(dep: str):
    """一键安装指定依赖"""
    cmds = {
        "agent-device": ["npm", "install", "-g", "agent-device"],
        "adbkeyboard":  None,  # APK 安装，前端处理
    }
    if dep not in cmds:
        return {"ok": False, "msg": f"不支持自动安装: {dep}"}
    cmd = cmds[dep]
    if cmd is None:
        return {"ok": False, "msg": "请手动安装 ADBKeyboard APK"}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {"ok": r.returncode == 0, "msg": r.stdout or r.stderr}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.post("/install-apk")
def install_apk():
    """通过 ADB 安装 ADBKeyboard APK"""
    apk_path = os.path.join(os.path.dirname(__file__), "../../resources/ADBKeyboard.apk")
    import os
    if not os.path.exists(apk_path):
        return {"ok": False, "msg": "APK 文件不存在，请将 ADBKeyboard.apk 放入 resources/ 目录"}
    try:
        r = subprocess.run(
            ["adb", "install", "-r", apk_path],
            capture_output=True, text=True, timeout=30
        )
        return {"ok": "Success" in r.stdout, "msg": r.stdout or r.stderr}
    except Exception as e:
        return {"ok": False, "msg": str(e)}
