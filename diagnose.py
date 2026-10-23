"""Explicit metadata binding/diagnosis; never starts bridge or sends messages."""
import argparse
import json
import os
from pathlib import Path

from window_binding import current_identity, initialize, assert_bound, verify_account


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handle', type=int, help='Explicitly reviewed small-account main-window handle')
    parser.add_argument('--nickname')
    parser.add_argument('--account-id', help='Stable WeChat ID, not display nickname')
    parser.add_argument('--binding', type=Path, default=Path(__file__).with_name('binding.local.json'))
    parser.add_argument('--verify-account', action='store_true', help='Open bound account profile to verify ID; no messaging')
    args = parser.parse_args()
    if args.handle is not None:
        if not args.nickname or not args.account_id:
            parser.error('--nickname and --account-id are required when binding')
        b = current_identity(args.handle)
        data = dict(handle=b.handle, pid=b.pid, started=b.started,
                    nickname=args.nickname, account_id=args.account_id)
        args.binding.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.environ['WEMAI_BINDING_FILE'] = str(args.binding.resolve())
    initialize()
    assert_bound()
    if args.verify_account:
        verify_account()
        print('Account profile verified. Bridge has NOT been started.')
    else:
        print('Window/process identity valid. Account profile and UI compatibility NOT verified.')


if __name__ == '__main__':
    main()
