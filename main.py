from __future__ import annotations

import asyncio
import logging
import os
import queue
import signal
import sys
import threading


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg_mod
from ws_client import WsPluginClient
from wx_listener import WeChatListener
from wx_sender import WeChatSender
import tomllib
from pathlib import Path
from safety_policy import GroupPolicy
from window_binding import initialize, verify_account, assert_bound

logger = logging.getLogger("wemai_client.main")
_stop_event = threading.Event()


def setup_logging(log_cfg: cfg_mod.LogConfig) -> None:
    os.makedirs(os.path.dirname(log_cfg.file) or ".", exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_cfg.level.upper(), logging.INFO),
        format=log_cfg.format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_cfg.file, encoding="utf-8"),
        ],
    )


def handle_signal(sig, frame) -> None:
    logger.info("收到信号 %s", sig)
    _stop_event.set()


class WeMaiClient:
    def __init__(self, cfg: cfg_mod.ClientConfig) -> None:
        policy_path = Path(__file__).with_name('safety.toml')
        settings = tomllib.loads(policy_path.read_text(encoding='utf-8'))
        self._policy = GroupPolicy(tuple(settings.get('groups', [])), settings.get('send_enabled') is True)
        if not self._policy.groups:
            raise RuntimeError('Explicit local group allowlist is required.')
        cfg.wechat.target_chats = list(self._policy.groups)
        cfg.wechat.admin_chats = []
        self._cfg = cfg
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws = WsPluginClient(
            host=cfg.connection.server_host,
            port=cfg.connection.server_port,
            reconnect_delay=cfg.connection.reconnect_delay,
        )
        self._outbound_queue: queue.Queue = queue.Queue()
        self._sender = WeChatSender(
            outbound_queue=self._outbound_queue,
            send_delay=cfg.wechat.send_delay,
            close_weixin=cfg.wechat.close_weixin,
        )
        self._listener: WeChatListener | None = None

    async def run(self) -> None:
        initialize()
        verify_account()
        self._loop = asyncio.get_running_loop()
        logger.info("=" * 50)
        logger.info("WeMai Client - 微信 × MaiBot 桥接客户端")
        logger.info("服务器: %s:%s", self._cfg.connection.server_host, self._cfg.connection.server_port)
        logger.info("=" * 50)

        self._ws.set_outbound_handler(self._on_plugin_outbound)
        self._ws.set_config_handler(self._on_config_update)

        listener = WeChatListener(
            target_chats=self._cfg.wechat.target_chats,
            excluded=self._cfg.wechat.excluded,
            poll_interval=1.0,
            close_weixin=self._cfg.wechat.close_weixin,
            send_delay=self._cfg.wechat.send_delay,
            on_message=self._on_wechat_message,
            group_members=self._cfg.wechat.group_members,
            include_muted=self._cfg.wechat.include_muted,
            on_friend_request=self._on_friend_request,
            admin_chats=self._cfg.wechat.admin_chats,
        )
        self._listener = listener
        
        # Wire sender to listener's dialog windows
        self._sender.set_dialog_windows(listener.get_dialog_windows())
        self._sender.set_pre_send_hook(listener.begin_send)
        self._sender.set_post_send_hook(listener.mark_sent)
        
        self._sender._safety_policy = self._policy
        self._sender.start()
        listener.start()

        ws_task = asyncio.create_task(self._ws.run())

        try:
            while not _stop_event.is_set():
                assert_bound()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            self._listener = None
            listener.stop()
            self._sender.stop()
            await self._ws.stop()
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass
            logger.info("所有组件已停止")

    def _on_config_update(self, msg: dict) -> None:
        # Remote configuration can only reduce local scope.
        if self._listener is not None:
            self._listener.merge_remote_targets(True, self._policy.remote_groups(msg.get('group_list', [])), [])
            self._listener._target_chats = self._policy.remote_groups(msg.get('group_list', []))

    def _handle_moment_command(self, msg: dict) -> None:
        return

    def _send_moment_response(self, req_id: str, data: dict) -> None:
        return

    def _on_wechat_message(self, msg: dict) -> None:
        if not self._policy.inbound(msg):
            return
        assert_bound()
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._ws.send_inbound(msg), self._loop)

    def _on_friend_request(self, msg: dict) -> None:
        return

    def _on_plugin_outbound(self, msg: dict) -> None:
        if not self._policy.outbound(msg):
            logger.warning('Outbound command rejected by local policy')
            return
        self._outbound_queue.put(msg)


async def async_main() -> None:
    cfg = cfg_mod.load_config()
    setup_logging(cfg.log)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    client = WeMaiClient(cfg)
    if not client._policy.send_enabled:
        logger.warning("Disabled by default. Use diagnose.py first; bridge was not started.")
        return
    await client.run()


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.getLogger("wemai_client.main").critical("异常退出: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
