# =========================================================
# CORE 5 – SYSTEM UTILITIES — Hardened
# =========================================================

import os
import time
import platform
import subprocess
import logging
import requests
from datetime import datetime

# --------------------------------------------------
# Dedicated logger for system-level actions.
# Every destructive/system-touching action gets logged here,
# separate from normal print() debug output, so you have a
# real audit trail if something unexpected happens.
# --------------------------------------------------
logging.basicConfig(
    filename="core5_system_actions.log",
    level=logging.INFO,
    format="%(asctime)s [Core 5] %(message)s"
)


class Core5SystemUtils:
    """
    Phase 2 – Core 5 (Hardened)
    ----------------------------
    Responsibility:
    - Provide safe, cross-platform system-level actions
    - Require explicit confirmation for destructive actions
    - Log every attempt (success or failure) for auditing
    - Never let raw/dynamic user input reach a shell command

    IMPORTANT (build-order rule):
    Do NOT wire shutdown/restart into Core 4's live routing until
    Core 18 (Security & Trust) provides a real permission check.
    The `require_confirmation` flag here is a stopgap, not a
    replacement for that.
    """

    def __init__(self, require_confirmation: bool = True):
        self.os_type = platform.system()  # "Windows", "Linux", "Darwin"
        self.require_confirmation = require_confirmation
        self._pending_action = None  # tracks an action awaiting confirmation

        # Previous samples, needed to compute delta-based metrics
        # (disk activity %, network kbps) — both require two points
        # in time, not just one snapshot.
        self._last_disk_io = None
        self._last_disk_time = None
        self._last_net_io = None
        self._last_net_time = None
        self._cpu_name_cache = None  # WMI lookup is slow-ish, cache once
        print(f"[Core 5] System utilities online (OS: {self.os_type})")
        logging.info(f"Core 5 initialized on {self.os_type}")

    # --------------------------------------------------
    # Safe informational utilities
    # --------------------------------------------------
    def get_time(self) -> str:
        return datetime.now().strftime("Current time is %I:%M %p")

    def get_date(self) -> str:
        return datetime.now().strftime("Today's date is %d %B %Y")

    # --------------------------------------------------
    # Destructive actions — require confirmation
    # --------------------------------------------------
    def shutdown(self, confirm: bool = False) -> str:
        return self._destructive_action("shutdown", confirm)

    def restart(self, confirm: bool = False) -> str:
        return self._destructive_action("restart", confirm)

    def cancel_shutdown(self) -> str:
        """Aborts a pending shutdown/restart (Windows/Linux support)."""
        try:
            if self.os_type == "Windows":
                result = subprocess.run(
                    ["shutdown", "/a"], capture_output=True, text=True, check=False
                )
            elif self.os_type == "Linux":
                result = subprocess.run(
                    ["shutdown", "-c"], capture_output=True, text=True, check=False
                )
            else:
                msg = f"Cancel not supported on {self.os_type}"
                logging.warning(msg)
                return msg

            self._pending_action = None

            if result.returncode == 0:
                logging.info("Pending shutdown/restart cancelled")
                return "Shutdown/restart cancelled."
            else:
                logging.info(f"Cancel attempted, nothing pending or failed: {result.stderr}")
                return "No pending shutdown to cancel."

        except Exception as e:
            logging.error(f"cancel_shutdown failed: {e}")
            return "Couldn't cancel — something went wrong."

    # --------------------------------------------------
    # Internal: confirmation-gated destructive action handler
    # --------------------------------------------------
    def _destructive_action(self, action: str, confirm: bool) -> str:
        if self.require_confirmation and not confirm:
            # First call: don't execute, ask for confirmation instead.
            self._pending_action = action
            logging.info(f"Action '{action}' requested but NOT confirmed — awaiting confirmation")
            return (
                f"Are you sure you want to {action}? "
                f"Say '{action} confirm' or call again with confirm=True."
            )

        # Confirmed (or confirmation disabled) — proceed.
        logging.info(f"Executing confirmed action: {action}")
        success, error = self._run_platform_command(action)

        self._pending_action = None

        if success:
            logging.info(f"Action '{action}' executed successfully")
            return f"{action.capitalize()} initiated."
        else:
            logging.error(f"Action '{action}' failed: {error}")
            return f"Failed to {action}: {error}"

    def _run_platform_command(self, action: str):
        """
        Runs the correct command per OS using subprocess with an
        argument LIST (never a shell string) — avoids injection risk
        entirely since there is no user-controlled input here.
        """
        try:
            if self.os_type == "Windows":
                if action == "shutdown":
                    cmd = ["shutdown", "/s", "/t", "5"]
                elif action == "restart":
                    cmd = ["shutdown", "/r", "/t", "5"]
                else:
                    return False, f"Unknown action: {action}"

            elif self.os_type == "Linux":
                if action == "shutdown":
                    cmd = ["shutdown", "-h", "+1"]  # 1 min delay
                elif action == "restart":
                    cmd = ["shutdown", "-r", "+1"]
                else:
                    return False, f"Unknown action: {action}"

            elif self.os_type == "Darwin":  # macOS
                if action == "shutdown":
                    cmd = ["sudo", "shutdown", "-h", "+1"]
                elif action == "restart":
                    cmd = ["sudo", "shutdown", "-r", "+1"]
                else:
                    return False, f"Unknown action: {action}"

            else:
                return False, f"Unsupported OS: {self.os_type}"

            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr.strip() or f"Exit code {result.returncode}"

        except FileNotFoundError:
            return False, "Shutdown command not found on this system"
        except Exception as e:
            return False, str(e)

    # --------------------------------------------------
    # Helper: check if there's an action waiting on confirmation
    # --------------------------------------------------
    def has_pending_action(self) -> bool:
        return self._pending_action is not None

    def get_pending_action(self):
        return self._pending_action

    # --------------------------------------------------
    # Volume & Audio controls (Windows only for now)
    # Uses virtual key codes via PowerShell — no extra packages needed.
    # 173 = VK_VOLUME_MUTE, 174 = VK_VOLUME_DOWN, 175 = VK_VOLUME_UP
    # --------------------------------------------------
    def volume_up(self) -> dict:
        return self._send_media_key(175, "volume_up")

    def volume_down(self) -> dict:
        return self._send_media_key(174, "volume_down")

    def mute(self) -> dict:
        return self._set_mute(True)

    def unmute(self) -> dict:
        return self._set_mute(False)

    def _set_mute(self, muted: bool) -> dict:
        try:
            import pythoncom
            pythoncom.CoInitialize()
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume_ctrl = cast(interface, POINTER(IAudioEndpointVolume))
                volume_ctrl.SetMute(muted, None)
                return {"success": True, "message": "Muted" if muted else "Unmuted", "muted": muted}
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            return {"success": False, "message": "pywin32/pycaw not installed — run: pip install pycaw comtypes pywin32"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _send_media_key(self, vk_code: int, label: str) -> dict:
        try:
            if self.os_type == "Windows":
                subprocess.run(
                    ["powershell", "-Command",
                     f"$wshell = New-Object -ComObject wscript.shell; "
                     f"$wshell.SendKeys([char]{vk_code})"],
                    capture_output=True, timeout=3
                )
                logging.info(f"{label} key sent")
                return {"success": True, "message": label.replace("_", " ").capitalize()}
            else:
                return {"success": False, "message": f"{label} not supported on {self.os_type} yet"}
        except Exception as e:
            logging.error(f"{label} failed: {e}")
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # Absolute volume get/set — needed for the drag slider.
    #
    # FIXED: AudioUtilities.GetSpeakers() was returning pycaw's own
    # simplified wrapper object (has .FriendlyName, not .Activate())
    # instead of the raw Windows audio interface — a known version
    # inconsistency in pycaw. This bypasses that wrapper entirely and
    # talks to Windows' IMMDeviceEnumerator directly, which is the
    # actual underlying interface pycaw itself wraps — not dependent
    # on which pycaw version/wrapper behavior is installed.
    # --------------------------------------------------
    def _get_volume_control(self):
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL, GUID, CoCreateInstance
        from pycaw.pycaw import IMMDeviceEnumerator, IAudioEndpointVolume

        CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
        enumerator = CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL
        )
        # eRender=0 (output devices), eMultimedia=1 (default multimedia role)
        # — this is the SAME device Windows' own volume slider controls.
        device = enumerator.GetDefaultAudioEndpoint(0, 1)
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def get_volume(self) -> dict:
        try:
            import pythoncom
            pythoncom.CoInitialize()
            try:
                volume_ctrl = self._get_volume_control()
                current = volume_ctrl.GetMasterVolumeLevelScalar()  # 0.0 - 1.0
                muted = volume_ctrl.GetMute()
                return {"success": True, "volume": round(current * 100), "muted": bool(muted)}
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            return {"success": False, "message": "pywin32/pycaw not installed — run: pip install pycaw comtypes pywin32"}
        except Exception as e:
            print(f"[get_volume] ❌ EXCEPTION: {e}")
            return {"success": False, "message": str(e)}

    def set_volume(self, level: int) -> dict:
        try:
            import pythoncom
            pythoncom.CoInitialize()
            try:
                level = max(0, min(100, int(level)))
                print(f"[set_volume] Requested level: {level}")

                volume_ctrl = self._get_volume_control()

                before = volume_ctrl.GetMasterVolumeLevelScalar()
                print(f"[set_volume] Volume BEFORE set: {round(before * 100)}%")

                volume_ctrl.SetMasterVolumeLevelScalar(level / 100.0, None)

                after = volume_ctrl.GetMasterVolumeLevelScalar()
                print(f"[set_volume] Volume AFTER set: {round(after * 100)}% (requested {level}%)")

                return {"success": True, "volume": level, "actual_after": round(after * 100)}
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            return {"success": False, "message": "pywin32/pycaw not installed — run: pip install pycaw comtypes pywin32"}
        except Exception as e:
            print(f"[set_volume] ❌ EXCEPTION: {e}")
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # Battery status
    # --------------------------------------------------
    def get_battery(self) -> dict:
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                return {"success": False, "message": "No battery detected (desktop PC?)"}
            return {
                "success": True,
                "percent": round(battery.percent, 1),
                "charging": battery.power_plugged,
                "message": (
                    f"{'Charging' if battery.power_plugged else 'On battery'} "
                    f"at {round(battery.percent)}%"
                ),
            }
        except ImportError:
            return {"success": False, "message": "psutil not installed — run: pip install psutil"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # CPU details — % (already had), plus GHz and the real friendly
    # name ("AMD Ryzen 7 7445HS"), not platform.processor()'s raw
    # string (which on Windows is something unreadable like
    # "AMD64 Family 25 Model 68..." — WMI is what actually has the
    # human-readable name, same proven PowerShell pattern used
    # elsewhere in this file, not a new interop approach).
    # --------------------------------------------------
    def get_cpu_details(self) -> dict:
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.3)
            freq = psutil.cpu_freq()
            ghz = round(freq.current / 1000, 2) if freq else None

            if self._cpu_name_cache is None:
                self._cpu_name_cache = self._get_cpu_name()

            return {
                "success": True,
                "cpu_percent": round(cpu_percent, 1),
                "cpu_ghz": ghz,
                "cpu_name": self._cpu_name_cache,
            }
        except ImportError:
            return {"success": False, "message": "psutil not installed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _get_cpu_name(self) -> str:
        try:
            if self.os_type != "Windows":
                return platform.processor() or "Unknown CPU"
            result = subprocess.run(
                ["powershell", "-Command", "(Get-WmiObject Win32_Processor).Name"],
                capture_output=True, text=True, timeout=5
            )
            name = result.stdout.strip()
            return name if name else (platform.processor() or "Unknown CPU")
        except Exception:
            return platform.processor() or "Unknown CPU"

    # --------------------------------------------------
    # Disk space per drive letter (separate from activity — this is
    # genuinely different data: how full each drive is, not how busy
    # the underlying physical disk is right now).
    # --------------------------------------------------
    def get_all_drives(self) -> dict:
        try:
            import psutil
            drives = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append({
                        "drive": part.device.rstrip("\\"),
                        "percent": round(usage.percent, 1),
                        "used_gb": round(usage.used / (1024 ** 3), 1),
                        "total_gb": round(usage.total / (1024 ** 3), 1),
                    })
                except (PermissionError, OSError):
                    continue  # e.g. an empty CD drive
            return {"success": True, "drives": drives}
        except ImportError:
            return {"success": False, "message": "psutil not installed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # Disk ACTIVITY % — per physical disk, matching what Task Manager
    # actually shows (one number per physical drive, not per letter —
    # C: and D: on the same NVMe drive would show identical numbers
    # anyway, since they share the same underlying hardware).
    #
    # Computed from the DELTA in read_time+write_time (milliseconds
    # psutil reports the disk spent busy) between two calls, divided
    # by the real time elapsed — this is the same underlying approach
    # Windows' own "% Active Time" counter uses.
    # --------------------------------------------------
    def get_disk_activity(self) -> dict:
        try:
            import psutil
            now = time.time()
            current_io = psutil.disk_io_counters(perdisk=True)

            if self._last_disk_io is None or self._last_disk_time is None:
                self._last_disk_io = current_io
                self._last_disk_time = now
                # First call — no delta possible yet
                disks = [{"name": name, "activity_percent": 0.0} for name in current_io]
                return {"success": True, "disks": disks}

            elapsed_ms = (now - self._last_disk_time) * 1000
            disks = []
            for name, counters in current_io.items():
                prev = self._last_disk_io.get(name)
                if prev is None or elapsed_ms <= 0:
                    disks.append({"name": name, "activity_percent": 0.0})
                    continue
                busy_delta_ms = (counters.read_time + counters.write_time) - (prev.read_time + prev.write_time)
                activity = max(0.0, min(100.0, (busy_delta_ms / elapsed_ms) * 100))
                disks.append({"name": name, "activity_percent": round(activity, 1)})

            self._last_disk_io = current_io
            self._last_disk_time = now
            return {"success": True, "disks": disks}
        except ImportError:
            return {"success": False, "message": "psutil not installed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # Network speed in kbps, Ethernet and WiFi tracked separately.
    # Same delta-over-time approach as disk activity above.
    # --------------------------------------------------
    def get_network_speed(self) -> dict:
        try:
            import psutil
            now = time.time()
            current_io = psutil.net_io_counters(pernic=True)

            if self._last_net_io is None or self._last_net_time is None:
                self._last_net_io = current_io
                self._last_net_time = now
                return {"success": True, "ethernet_kbps": 0.0, "wifi_kbps": 0.0}

            elapsed = now - self._last_net_time
            ethernet_kbps = 0.0
            wifi_kbps = 0.0

            for name, counters in current_io.items():
                prev = self._last_net_io.get(name)
                if prev is None or elapsed <= 0:
                    continue
                bytes_delta = (counters.bytes_sent + counters.bytes_recv) - (prev.bytes_sent + prev.bytes_recv)
                kbps = round((bytes_delta * 8 / 1000) / elapsed, 1)

                lname = name.lower()
                if "wi-fi" in lname or "wifi" in lname or "wlan" in lname:
                    wifi_kbps = kbps
                elif "ethernet" in lname or "eth" in lname:
                    ethernet_kbps = kbps

            self._last_net_io = current_io
            self._last_net_time = now
            return {"success": True, "ethernet_kbps": ethernet_kbps, "wifi_kbps": wifi_kbps}
        except ImportError:
            return {"success": False, "message": "psutil not installed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # System info — CPU, RAM, disk
    # --------------------------------------------------
    def get_system_info(self) -> dict:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk_path = "C:\\" if self.os_type == "Windows" else "/"
            disk = psutil.disk_usage(disk_path)
            return {
                "success": True,
                "cpu_percent": round(cpu, 1),
                "ram_percent": round(mem.percent, 1),
                "ram_used_gb": round(mem.used / (1024 ** 3), 1),
                "ram_total_gb": round(mem.total / (1024 ** 3), 1),
                "disk_percent": round(disk.percent, 1),
                "disk_used_gb": round(disk.used / (1024 ** 3), 1),
                "disk_total_gb": round(disk.total / (1024 ** 3), 1),
            }
        except ImportError:
            return {"success": False, "message": "psutil not installed — run: pip install psutil"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # GPU stats (NVIDIA only — via the bundled nvidia-smi tool)
    # --------------------------------------------------
    def get_gpu_info(self) -> dict:
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return {"success": False, "message": "nvidia-smi not available (no NVIDIA GPU or drivers?)"}

            parts = [p.strip() for p in result.stdout.strip().split(",")]
            name, util, temp, mem_used, mem_total = parts
            return {
                "success": True,
                "gpu_name": name,
                "gpu_percent": float(util),
                "gpu_temp_c": float(temp),
                "vram_used_mb": float(mem_used),
                "vram_total_mb": float(mem_total),
                "vram_percent": round((float(mem_used) / float(mem_total)) * 100, 1),
            }
        except FileNotFoundError:
            return {"success": False, "message": "nvidia-smi not found — no NVIDIA GPU detected"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --------------------------------------------------
    # CPU temperature & fan speed — via LibreHardwareMonitor's
    # Remote Web Server. Windows has no reliable built-in way to read
    # either of these, so this reads them from LHM's local JSON feed
    # instead — you need LHM running with the Remote Web Server
    # enabled (Options > Remote Web Server > Run) for this to work.
    # --------------------------------------------------
    def _query_lhm(self):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=3)
            if response.status_code != 200:
                return None
            return response.json()
        except Exception:
            return None

    def _find_lhm_sensor(self, node, keywords):
        """Recursively searches LHM's JSON hardware tree for a sensor
        whose label matches any of the given keywords. LHM's tree
        shape varies by motherboard/CPU, so we search by name rather
        than a fixed path."""
        text = node.get("Text", "")
        value = node.get("Value", "")
        if value and value != "-" and any(kw.lower() in text.lower() for kw in keywords):
            return value
        for child in node.get("Children", []):
            result = self._find_lhm_sensor(child, keywords)
            if result:
                return result
        return None

    def _parse_lhm_number(self, raw_value: str):
        import re
        match = re.search(r"[-+]?\d*\.?\d+", raw_value)
        return float(match.group()) if match else None

    def get_cpu_temperature(self) -> dict:
        data = self._query_lhm()
        if data is None:
            return {"success": False,
                    "message": "LibreHardwareMonitor not running, or Remote Web Server not enabled"}

        raw = self._find_lhm_sensor(data, ["CPU Package", "Core Max", "CPU Temperature"])
        if raw is None:
            return {"success": False, "message": "No CPU temperature sensor found in LibreHardwareMonitor"}

        temp = self._parse_lhm_number(raw)
        if temp is None:
            return {"success": False, "message": f"Could not parse temperature value: {raw}"}
        return {"success": True, "temp_c": temp}

    def get_fan_speed(self) -> dict:
        data = self._query_lhm()
        if data is None:
            return {"success": False,
                    "message": "LibreHardwareMonitor not running, or Remote Web Server not enabled"}

        raw = self._find_lhm_sensor(data, ["CPU Fan", "System Fan", "Fan #1", "Fan #2"])
        if raw is None:
            return {"success": False, "message": "No fan sensor found in LibreHardwareMonitor"}

        rpm = self._parse_lhm_number(raw)
        if rpm is None:
            return {"success": False, "message": f"Could not parse fan speed value: {raw}"}
        return {"success": True, "rpm": round(rpm)}

    # --------------------------------------------------
    # Screen brightness — via WMI (built-in laptop display only)
    # --------------------------------------------------
    def get_brightness(self) -> dict:
        try:
            ps_get = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
            result = subprocess.run(["powershell", "-Command", ps_get], capture_output=True, text=True, timeout=5)
            current = result.stdout.strip()
            if not current:
                return {"success": False, "message": "No WMI brightness data — external monitor or unsupported display"}
            return {"success": True, "brightness": int(current)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def set_brightness(self, level: int) -> dict:
        try:
            level = max(0, min(100, level))
            ps_command = (
                f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)."
                f"WmiSetBrightness(1, {level})"
            )
            subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True, timeout=5
            )
            return {"success": True, "brightness": level, "message": f"Brightness set to {level}%"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def brightness_up(self) -> dict:
        return self._adjust_brightness(10)

    def brightness_down(self) -> dict:
        return self._adjust_brightness(-10)

    def _adjust_brightness(self, delta: int) -> dict:
        current_result = self.get_brightness()
        current = current_result.get("brightness", 50) if current_result.get("success") else 50
        return self.set_brightness(current + delta)

    # --------------------------------------------------
    # WiFi / Bluetooth on-off — via the Windows.Devices.Radios API.
    # This is the SAME mechanism Windows' own Quick Settings panel
    # uses internally — it does NOT require admin rights, unlike
    # netsh or Disable-PnpDevice (which would silently fail since
    # Zephyr runs as a normal user process, not elevated).
    # --------------------------------------------------
    def wifi_on(self) -> dict:
        return self._toggle_radio("WiFi", True)

    def wifi_off(self) -> dict:
        return self._toggle_radio("WiFi", False)

    def bluetooth_on(self) -> dict:
        return self._toggle_radio("Bluetooth", True)

    def bluetooth_off(self) -> dict:
        return self._toggle_radio("Bluetooth", False)

    def get_wifi_state(self) -> dict:
        return self._get_radio_state("WiFi")

    def get_bluetooth_state(self) -> dict:
        return self._get_radio_state("Bluetooth")

    def _get_radio_state(self, kind: str) -> dict:
        """Read-only — reads current state without changing anything.
        Reuses the same reliable Radios API path as the on/off toggle."""
        try:
            script = f'''
try {{
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
    Function Await($WinRtTask, $ResultType) {{
        $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
        $netTask = $asTask.Invoke($null, @($WinRtTask))
        $netTask.Wait(-1) | Out-Null
        $netTask.Result
    }}
    [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null

    $accessStatus = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
    if ($accessStatus -ne 'Allowed') {{ Write-Output "RESULT:ACCESS_DENIED"; exit }}

    $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    $target = $radios | Where-Object {{ $_.Kind -eq '{kind}' }} | Select-Object -First 1
    if ($null -eq $target) {{ Write-Output "RESULT:NOT_FOUND"; exit }}

    Write-Output "RESULT:$($target.State)"
}} catch {{
    Write-Output "EXCEPTION:$($_.Exception.Message)"
}}
'''
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, text=True, timeout=8
            )
            lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
            final_line = next((l for l in lines if l.startswith("RESULT:")), None)
            final_value = final_line.split(":", 1)[1] if final_line else None

            if final_value in ("On", "Off"):
                return {"success": True, "state": final_value, "on": final_value == "On"}
            if final_value == "NOT_FOUND":
                return {"success": False, "message": f"No {kind} radio found"}
            if final_value == "ACCESS_DENIED":
                return {"success": False, "message": f"{kind} access denied"}
            return {"success": False, "message": f"Unexpected output: {lines}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _toggle_radio(self, kind: str, enable: bool) -> dict:
        try:
            target_state = "On" if enable else "Off"
            # DIAGNOSTIC VERSION: explicitly captures the access status
            # (RequestAccessAsync can silently return "Denied" for
            # non-packaged callers like plain PowerShell, especially
            # for Bluetooth) and wraps everything in try/catch so any
            # .NET exception is actually visible instead of swallowed.
            script = f'''
try {{
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
    Function Await($WinRtTask, $ResultType) {{
        $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
        $netTask = $asTask.Invoke($null, @($WinRtTask))
        $netTask.Wait(-1) | Out-Null
        $netTask.Result
    }}
    [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null

    $accessStatus = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
    Write-Output "ACCESS_STATUS:$accessStatus"

    if ($accessStatus -ne 'Allowed') {{
        Write-Output "RESULT:ACCESS_DENIED"
        exit
    }}

    $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    Write-Output "RADIO_COUNT:$($radios.Count)"

    $target = $radios | Where-Object {{ $_.Kind -eq '{kind}' }} | Select-Object -First 1
    if ($null -eq $target) {{ Write-Output "RESULT:NOT_FOUND"; exit }}

    Write-Output "CURRENT_STATE:$($target.State)"
    $setResult = Await ($target.SetStateAsync('{target_state}')) ([Windows.Devices.Radios.RadioAccessStatus])
    Write-Output "SET_RESULT:$setResult"
    Write-Output "RESULT:$($target.State)"
}} catch {{
    Write-Output "EXCEPTION:$($_.Exception.Message)"
}}
'''
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, text=True, timeout=10
            )
            lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
            print(f"[{kind} toggle] Full diagnostic output: {lines}")

            final_line = next((l for l in lines if l.startswith("RESULT:")), None)
            final_value = final_line.split(":", 1)[1] if final_line else None

            if final_value == "ACCESS_DENIED":
                access_line = next((l for l in lines if l.startswith("ACCESS_STATUS:")), "")
                return {"success": False,
                        "message": f"{kind} access denied by Windows ({access_line}). "
                                   f"This is a known restriction for non-packaged apps — see console for full diagnostic."}
            if final_value == "NOT_FOUND":
                return {"success": False, "message": f"No {kind} radio found on this device"}
            if final_value in ("On", "Off"):
                return {"success": True, "message": f"{kind} turned {final_value}", "state": final_value}

            exception_line = next((l for l in lines if l.startswith("EXCEPTION:")), None)
            if exception_line:
                return {"success": False, "message": exception_line}

            return {"success": False, "message": f"Unexpected output: {lines or result.stderr[:200]}"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    utils = Core5SystemUtils(require_confirmation=True)

    print(utils.get_time())
    print(utils.get_date())

    # First call — NOT executed, just asks for confirmation
    print(utils.shutdown())
    print("Pending action:", utils.get_pending_action())

    # Second call, now confirmed — this WOULD actually shut down the
    # machine if uncommented, so it's left commented for safety in this demo.
    # print(utils.shutdown(confirm=True))

    # Cancel a pending shutdown/restart
    print(utils.cancel_shutdown())