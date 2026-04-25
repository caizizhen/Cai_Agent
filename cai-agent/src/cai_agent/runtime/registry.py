from __future__ import annotations

from typing import Any

from cai_agent.runtime.base import RuntimeBackend
from cai_agent.runtime.daytona_stub import DaytonaRuntime
from cai_agent.runtime.docker import DockerRuntime
from cai_agent.runtime.local import LocalRuntime
from cai_agent.runtime.modal_stub import ModalRuntime
from cai_agent.runtime.singularity_stub import SingularityRuntime
from cai_agent.runtime.ssh import SSHRuntime

RUNTIME_REGISTRY: dict[str, type[RuntimeBackend] | Any] = {
    "local": LocalRuntime,
    "docker": DockerRuntime,
    "ssh": SSHRuntime,
    "modal": ModalRuntime,
    "daytona": DaytonaRuntime,
    "singularity": SingularityRuntime,
}


def build_runtime_backend_interface_payload() -> dict[str, Any]:
    """HM-N11-D02: unified backend interface contract for local/docker/ssh/cloud stubs."""
    return {
        "schema_version": "runtime_backend_interface_v1",
        "operations": {
            "exec": {
                "args": ["cmd", "cwd", "env", "timeout_sec"],
                "result_schema": "exec_result_v1",
            },
            "exists": {
                "args": [],
                "result_type": "bool",
            },
            "describe": {
                "args": [],
                "result_type": "object",
            },
            "ensure_workspace": {
                "args": ["path"],
                "result_type": "void",
                "optional": True,
            },
        },
        "backends": {
            "local": {
                "status": "ga",
                "config_keys": [],
            },
            "docker": {
                "status": "ga",
                "config_keys": [
                    "runtime_docker_container",
                    "runtime_docker_image",
                    "runtime_docker_workdir",
                    "runtime_docker_volume_mounts",
                    "runtime_docker_exec_options",
                    "runtime_docker_cpus",
                    "runtime_docker_memory",
                ],
                "interface_alignment": {
                    "base_ops_aligned": True,
                    "describe_fields": ["mode", "workdir", "volume_mounts", "cpus", "memory"],
                },
            },
            "ssh": {
                "status": "ga",
                "config_keys": [
                    "runtime_ssh_host",
                    "runtime_ssh_user",
                    "runtime_ssh_key_path",
                    "runtime_ssh_strict_host_key",
                    "runtime_ssh_known_hosts_path",
                    "runtime_ssh_connect_timeout_sec",
                    "runtime_ssh_audit_log_path",
                    "runtime_ssh_audit_label",
                    "runtime_ssh_audit_include_command",
                ],
                "interface_alignment": {
                    "base_ops_aligned": True,
                    "describe_fields": ["host", "user", "connect_timeout_sec", "audit_enabled"],
                },
            },
            "modal": {
                "status": "conditional_stub",
                "config_keys": ["runtime_modal_app_name", "runtime_modal_hibernate_idle_seconds"],
            },
            "daytona": {
                "status": "conditional_stub",
                "config_keys": ["runtime_daytona_workspace"],
            },
            "singularity": {
                "status": "conditional_stub",
                "config_keys": ["runtime_singularity_sif_path", "runtime_singularity_bind_paths"],
            },
        },
    }


def get_runtime_backend(
    name: str,
    *,
    settings: Any | None = None,
) -> RuntimeBackend:
    """Instantiate a backend; reads ``[runtime]`` / ``[runtime.<name>]`` from ``settings`` when given."""
    key = (name or "local").strip().lower() or "local"
    cls = RUNTIME_REGISTRY.get(key)
    if cls is None:
        return LocalRuntime()
    if key == "local":
        return LocalRuntime()
    if key == "docker":
        container = ""
        image = ""
        workdir = "/workspace"
        volume_mounts: tuple[str, ...] = ()
        exec_opts: tuple[str, ...] = ()
        cpus = mem = None
        if settings is not None:
            container = str(getattr(settings, "runtime_docker_container", "") or "").strip()
            image = str(getattr(settings, "runtime_docker_image", "") or "").strip()
            workdir = str(getattr(settings, "runtime_docker_workdir", "/workspace") or "/workspace").strip()
            vm = getattr(settings, "runtime_docker_volume_mounts", ()) or ()
            volume_mounts = tuple(str(x) for x in vm if str(x).strip())
            eo = getattr(settings, "runtime_docker_exec_options", ()) or ()
            exec_opts = tuple(str(x) for x in eo if str(x).strip())
            cpus = getattr(settings, "runtime_docker_cpus", None)
            mem = getattr(settings, "runtime_docker_memory", None)
            cpus = str(cpus).strip() if cpus else None
            mem = str(mem).strip() if mem else None
        return DockerRuntime(
            container=container,
            image=image,
            workdir=workdir,
            volume_mounts=volume_mounts,
            exec_options=exec_opts,
            cpus=cpus,
            memory=mem,
        )
    if key == "ssh":
        host = user = ""
        key_path = None
        strict = True
        khosts = None
        ct = 15.0
        audit_log_path = None
        audit_label = None
        audit_include_command = False
        if settings is not None:
            host = str(getattr(settings, "runtime_ssh_host", "") or "")
            user = str(getattr(settings, "runtime_ssh_user", "") or "")
            kp = getattr(settings, "runtime_ssh_key_path", None)
            key_path = str(kp).strip() if kp else None
            strict = bool(getattr(settings, "runtime_ssh_strict_host_key", True))
            kh = getattr(settings, "runtime_ssh_known_hosts_path", None)
            khosts = str(kh).strip() if kh else None
            ct = float(getattr(settings, "runtime_ssh_connect_timeout_sec", 15.0) or 15.0)
            ap = getattr(settings, "runtime_ssh_audit_log_path", None)
            audit_log_path = str(ap).strip() if ap else None
            al = getattr(settings, "runtime_ssh_audit_label", None)
            audit_label = str(al).strip() if al else None
            audit_include_command = bool(getattr(settings, "runtime_ssh_audit_include_command", False))
        return SSHRuntime(
            host=host,
            user=user,
            key_path=key_path,
            strict_host_key=strict,
            known_hosts_path=khosts,
            connect_timeout_sec=ct,
            audit_log_path=audit_log_path,
            audit_label=audit_label,
            audit_include_command=audit_include_command,
        )
    if key == "modal":
        app = ""
        hib: int | None = None
        if settings is not None:
            app = str(getattr(settings, "runtime_modal_app_name", "") or "")
            hib = getattr(settings, "runtime_modal_hibernate_idle_seconds", None)
        return ModalRuntime(app_name=app, hibernate_idle_seconds=hib)
    if key == "daytona":
        ws = ""
        if settings is not None:
            ws = str(getattr(settings, "runtime_daytona_workspace", "") or "").strip()
        return DaytonaRuntime(workspace=ws)
    if key == "singularity":
        sif = ""
        binds: tuple[str, ...] = ()
        if settings is not None:
            sif = str(getattr(settings, "runtime_singularity_sif_path", "") or "").strip()
            bp = getattr(settings, "runtime_singularity_bind_paths", ()) or ()
            binds = tuple(str(x).strip() for x in bp if str(x).strip())
        return SingularityRuntime(sif_path=sif, bind_paths=binds)
    return LocalRuntime()


def list_runtimes_payload() -> dict[str, Any]:
    iface = build_runtime_backend_interface_payload()
    return {
        "schema_version": "runtime_registry_v1",
        "backends": sorted(RUNTIME_REGISTRY.keys()),
        "interface": iface,
    }
