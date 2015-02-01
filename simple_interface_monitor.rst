======================================
class SimpleInterfaceMonitor(OvsdbMonitor):
======================================


class SimpleInterfaceMonitor(OvsdbMonitor):
==========================================

OvsDbMonitorが理解できていれば、簡単。

初期化::

    def __init__(self, root_helper=None, respawn_interval=None):
        super(SimpleInterfaceMonitor, self).__init__(
            'Interface',
            columns=['name', 'ofport'],
            format='json',
            root_helper=root_helper,
            respawn_interval=respawn_interval,
        )
        self.data_received = False

SimpleInterfaceMonitorの初期化として、OvsDbMonitorにInterfaceテーブル、カラムとしてname、ofportの監視を行う。

アクティブかどうかのチェック::

    @property
    def is_active(self):
        return (self.data_received and
                self._kill_event and
                not self._kill_event.ready())

データを受信しているかつ、_kill_eventが設定されている（初期化されている）、_kill_eventが受信していない。

アップデートされているかどうかのチェック::

    @property
    def has_updates(self):
        """Indicate whether the ovsdb Interface table has been updated.

        True will be returned if the monitor process is not active.
        This 'failing open' minimizes the risk of falsely indicating
        the absence of updates at the expense of potential false
        positives.
        """
        return bool(list(self.iter_stdout())) or not self.is_active

標準出力にデータがある、かつ、is_activeがfalseの場合はupdateがあるという判定をする。is_activeがfalseの時に判定しているのは、上記コメントにもあるが、ovsの障害発生時(あるいは、killメソッドが呼び出されたあとなどに)に再度復旧動作を行うためだと思う(要調査)

スタートするメソッド::

    def start(self, block=False, timeout=5):
        super(SimpleInterfaceMonitor, self).start()
        if block:
            eventlet.timeout.Timeout(timeout)
            while not self.is_active:
                eventlet.sleep()

OvsDbMonitorとの違いは、block引数がTrueの場合は、is_activeがTrueになるまで待つこと。

強制終了::

    def _kill(self, *args, **kwargs):
        self.data_received = False
        super(SimpleInterfaceMonitor, self)._kill(*args, **kwargs)

OvsDbMonitorとの実装の違いは、data_receivedがFalseに設定されること。

標準出力からの読み込み::

    def _read_stdout(self):
        data = super(SimpleInterfaceMonitor, self)._read_stdout()
        if data and not self.data_received:
            self.data_received = True
        return data


OvsDbMonitorとの違いは、data_receivedのフラグを設定すること。

