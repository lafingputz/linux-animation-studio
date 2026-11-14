"""Platform-aware light/dark preference selection for LAS.

Keep the decision logic separate from Qt so it can be tested in headless builds.
"""


def windows_apps_use_light_theme():
    """Read the Windows *app* theme; None if unavailable or unconfigured."""
    try:
        import winreg
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
            return bool(int(value))
    except (ImportError, OSError, TypeError, ValueError):
        return None


def resolve_system_theme(platform_name, *, windows_light=None, qt_scheme=None, fallback_dark=False):
    """Resolve to 'Dark' or 'Light'. Qt scheme: 0 unknown, 1 light, 2 dark."""
    if platform_name == 'win32' and windows_light is not None:
        return 'Light' if windows_light else 'Dark'
    if qt_scheme == 2:
        return 'Dark'
    if qt_scheme == 1:
        return 'Light'
    return 'Dark' if fallback_dark else 'Light'
