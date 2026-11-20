"""Selección explícita de perfiles; v1.0 es siempre el valor por defecto."""
from importlib import import_module

STACKS = {"v1.0": "v1_0", "v1.1": "v1_1"}


def get_profile(stack: str, profile: str) -> dict:
    if stack not in STACKS:
        raise ValueError(f"stack desconocido: {stack}; use v1.0 o v1.1")
    profiles = import_module(f".{STACKS[stack]}", __name__).PROFILES
    if profile not in profiles:
        raise ValueError(f"perfil desconocido: {profile}; use {', '.join(profiles)}")
    return dict(profiles[profile])
