==========================
OvsDbMonitor
==========================

class OvsdbMonitor(async_process.AsyncProcess):
===============================================

AsyncProcessの内容が分かっていれば理解は簡単。

初期化::

    def __init__(self, table_name, columns=None, format=None,
                 root_helper=None, respawn_interval=None):

        cmd = ['ovsdb-client', 'monitor', table_name]
        if columns:
            cmd.append(','.join(columns))
        if format:
            cmd.append('--format=%s' % format)
        super(OvsdbMonitor, self).__init__(cmd,
                                           root_helper=root_helper,
                                           respawn_interval=respawn_interval)

ovs-clientを使用した処理を行うため、superにovs-clientの設定（第１引数）をしている。

標準出力の読み込み::

    def _read_stdout(self):
        data = self._process.stdout.readline()
        if not data:
            return
        #TODO(marun) The default root helper outputs exit errors to
        # stdout due to bug #1219530.  This check can be moved to
        # _read_stderr once the error is correctly output to stderr.
        if self.root_helper and self.root_helper in data:
            self._stderr_lines.put(data)
            LOG.error(_('Error received from ovsdb monitor: %s') % data)
        else:
            self._stdout_lines.put(data)
            LOG.debug(_('Output received from ovsdb monitor: %s') % data)
            return data

標準エラーを書き出せないバグの対処を実施している。

標準エラーの読み込み::

    def _read_stderr(self):
        data = super(OvsdbMonitor, self)._read_stderr()
        if data:
            LOG.error(_('Error received from ovsdb monitor: %s') % data)
            # Do not return value to ensure that stderr output will
            # stop the monitor.

エラーが発生した場合にログに書き出す処理が追加されている。

