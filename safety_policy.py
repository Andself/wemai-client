"""Local policy is authoritative; remote settings cannot expand it."""
from dataclasses import dataclass


class BindingError(RuntimeError):
    pass


@dataclass(frozen=True)
class WindowIdentity:
    handle: int
    pid: int
    started: float

    def validate(self, current: 'WindowIdentity') -> None:
        if self.handle <= 0 or self.pid <= 0 or self.started <= 0 or self != current:
            raise BindingError('Bound WeChat window/process changed; restart and bind again.')


@dataclass(frozen=True)
class GroupPolicy:
    groups: tuple[str, ...]
    send_enabled: bool = False

    def inbound(self, message: dict) -> bool:
        return (message.get('type') == 'inbound'
                and message.get('is_group') is True
                and message.get('chat') in self.groups)

    def outbound(self, message: dict) -> bool:
        return (self.send_enabled and message.get('type') == 'outbound'
                and message.get('receiver') in self.groups
                and bool(message.get('segments')))

    def remote_groups(self, groups: list[str]) -> list[str]:
        return [g for g in groups if g in self.groups]
