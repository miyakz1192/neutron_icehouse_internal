=========================================
class BasePollingManager(object):
=========================================


class BasePollingManager(object):
==================================

初期化::

    def __init__(self, root_helper=None,
                 ovsdb_monitor_respawn_interval=(
                     constants.DEFAULT_OVSDBMON_RESPAWN)):

        super(InterfacePollingMinimizer, self).__init__()
        self._monitor = ovsdb_monitor.SimpleInterfaceMonitor(
            root_helper=root_helper,
            respawn_interval=ovsdb_monitor_respawn_interval)

OvsDbMonitorの開始::

    def start(self):
        self._monitor.start()

OvsDbMonitorの開始::

    def stop(self):
        self._monitor.stop()

pollingが必要かどうか::

    def _is_polling_required(self):
        # Maximize the chances of update detection having a chance to
        # collect output.
        eventlet.sleep()
        return self._monitor.has_updates


