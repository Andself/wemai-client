"""Explicit session binding. No title-only fallback and no persisted HWND reuse."""
import json
import os
from pathlib import Path

from safety_policy import BindingError, WindowIdentity

_identity = None
_account_id = None
_nickname = None


def current_identity(handle):
    import psutil
    import win32gui
    import win32process
    if not win32gui.IsWindow(handle):
        raise BindingError('Bound window no longer exists.')
    _, pid = win32process.GetWindowThreadProcessId(handle)
    process = psutil.Process(pid)
    if process.name().lower() != 'weixin.exe':
        raise BindingError('Bound window is not Weixin.exe.')
    # Multiple account roots inside one process cannot be isolated by PID.
    roots = []
    def visit(hwnd, _):
        _, owner = win32process.GetWindowThreadProcessId(hwnd)
        if owner == pid and win32gui.GetWindowText(hwnd) in ('微信', 'Weixin'):
            if win32gui.IsWindowVisible(hwnd):
                roots.append(hwnd)
    win32gui.EnumWindows(visit, None)
    if handle not in roots or len(roots) != 1:
        raise BindingError('Expected one unambiguous account root in bound process.')
    return WindowIdentity(handle, pid, process.create_time())


def initialize():
    global _identity, _nickname, _account_id
    path = os.environ.get('WEMAI_BINDING_FILE')
    if not path:
        raise BindingError('Set WEMAI_BINDING_FILE to an explicitly reviewed session binding.')
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    _identity = WindowIdentity(int(d['handle']), int(d['pid']), float(d['started']))
    _nickname = str(d['nickname'])
    _account_id = str(d['account_id'])
    if not _nickname or not _account_id:
        raise BindingError('Nickname and stable WeChat account ID are required.')
    assert_bound()


def assert_bound():
    if _identity is None:
        raise BindingError('No account window bound. Refusing automatic discovery.')
    _identity.validate(current_identity(_identity.handle))
    return _identity


def validate_handle(handle):
    import win32process
    b = assert_bound()
    _, pid = win32process.GetWindowThreadProcessId(handle)
    if pid != b.pid:
        raise BindingError('Window belongs to another WeChat process.')


def verify_account():
    # Called before starting workers and immediately before each outgoing item.
    from pyweixin import Contacts
    b = assert_bound()
    assert_ui_access(b.handle)
    info = Contacts.check_my_info(close_weixin=False)
    if info.get('昵称') != _nickname or info.get('微信号') != _account_id:
        raise BindingError('Account identity mismatch; sending prohibited.')
    b.validate(current_identity(b.handle))


def assert_ui_access(handle):
    """Reject render-only roots before profile clicks or any worker starts."""
    root = Desktop(backend='uia').window(handle=handle)
    if not root.descendants(control_type='Button'):
        raise BindingError(
            'WeChat exposes no UIA buttons for this account. '
            'This UIA build cannot read or send; an OCR backend is required. '
            'Do not enable the bridge or switch to the primary account.'
        )


def find_window(class_name, title):
    import win32gui
    import win32process
    b = assert_bound()
    if title in ('微信', 'Weixin') and class_name == 'Qt51514QWindowIcon':
        return b.handle
    matches = []
    def visit(hwnd, _):
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == b.pid and (not title or win32gui.GetWindowText(hwnd) == title):
            if not class_name or win32gui.GetClassName(hwnd) == class_name:
                matches.append(hwnd)
    win32gui.EnumWindows(visit, None)
    if len(matches) != 1:
        raise BindingError('No unique matching window in bound process.')
    return matches[0]


class Desktop:
    def __init__(self, **kwargs):
        from pywinauto import Desktop as NativeDesktop
        self._desktop = NativeDesktop(**kwargs)

    def window(self, **kwargs):
        b = assert_bound()
        if 'handle' in kwargs:
            validate_handle(kwargs['handle'])
        if 'process' in kwargs and kwargs['process'] != b.pid:
            raise BindingError('Cross-account process selector denied.')
        kwargs['process'] = b.pid
        return self._desktop.window(**kwargs)
