=========================================
class BasePollingManager(object):
=========================================


class BasePollingManager(object):
==================================

初期化::

    def __init__(self):
        self._force_polling = False
        self._polling_completed = True

pollingの強制::

    def force_polling(self):
        self._force_polling = True

pollingが完了したことにするメソッド::

    def polling_completed(self):
        self._polling_completed = True

pollingが完了したかどうか(未実装)::

    def _is_polling_required(self):
        raise NotImplemented

pollingが必要かどうかを判定するメソッド::

    @property
    def is_polling_required(self):
        # Always consume the updates to minimize polling.
        polling_required = self._is_polling_required()

        # Polling is required regardless of whether updates have been
        # detected.
        if self._force_polling:
            self._force_polling = False
            polling_required = True

        # Polling is required if not yet done for previously detected
        # updates.
        if not self._polling_completed:
            polling_required = True

        if polling_required:
            # Track whether polling has been completed to ensure that
            # polling can be required until the caller indicates via a
            # call to polling_completed() that polling has been
            # successfully performed.
            self._polling_completed = False

        return polling_required


BasePollingManagerの派生クラスでは_is_polling_requiredを実装する（テンプレートメソッドパターン)。
_is_polling_requiredを呼び出して、polling_requiredに結果を格納。_force_pollingがTrueの場合は、_force_pollingをFalseに設定し、polling_requiredをTrueに設定する。
_polling_completedがFalseの場合はpolling_requiredがTrueに設定される。
polling_requiredがTrueの時、_polling_completedはFalseに設定され、このメソッドの復帰値としてpolling_requiredが返される。


