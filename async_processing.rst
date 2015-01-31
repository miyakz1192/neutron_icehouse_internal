===============================================
非同期プロセス管理
===============================================

AsyncProcess(object):
======================

プログラムを非同時実行するためのクラス
neutron/agent/linux/async_process.py

_reset_queues(キューのリセット)::

    def _reset_queues(self):
        self._stdout_lines = eventlet.queue.LightQueue()
        self._stderr_lines = eventlet.queue.LightQueue()

LightQueueの仕様がよくわからいので調査が必要。

start(スタート)::

    def start(self):
        """Launch a process and monitor it asynchronously."""
        if self._kill_event:
            raise AsyncProcessException(_('Process is already started'))
        else:
            LOG.debug(_('Launching async process [%s].'), self.cmd)
            self._spawn()

stop(ストップ)::

    def stop(self):
        """Halt the process and watcher threads."""
        if self._kill_event:
            LOG.debug(_('Halting async process [%s].'), self.cmd)
            self._kill()
        else:
            raise AsyncProcessException(_('Process is not running.'))

プロセスの起動(_spawn)::
 
    def _spawn(self):
        """Spawn a process and its watchers."""
        self._kill_event = eventlet.event.Event()
        self._process, cmd = utils.create_process(self.cmd,
                                                  root_helper=self.root_helper)
        self._watchers = []
        for reader in (self._read_stdout, self._read_stderr):
            # Pass the stop event directly to the greenthread to
            # ensure that assignment of a new event to the instance
            # attribute does not prevent the greenthread from using
            # the original event.
            watcher = eventlet.spawn(self._watch_process,
                                     reader,
                                     self._kill_event)
            self._watchers.append(watcher)


プロセスの起動とそれを監視するスレッドを起動しているっぽい。
create_processでutils.subprocess_popenでプロセスを起動している。

プロセスの強制終了(kill)::

   def _kill(self, respawning=False):
        """Kill the process and the associated watcher greenthreads.

        :param respawning: Optional, whether respawn will be subsequently
               attempted.
        """
        # Halt the greenthreads
        self._kill_event.send()

        pid = self._get_pid_to_kill()
        if pid:
            self._kill_process(pid)

        if not respawning:
            # Clear the kill event to ensure the process can be
            # explicitly started again.
            self._kill_event = None

強制終了すべきプロセスIDの取得(_get_pid_to_kill)::

    def _get_pid_to_kill(self):
        pid = self._process.pid
        # If root helper was used, two or more processes will be created:
        #
        #  - a root helper process (e.g. sudo myscript)
        #  - possibly a rootwrap script (e.g. neutron-rootwrap)
        #  - a child process (e.g. myscript)
        #
        # Killing the root helper process will leave the child process
        # running, re-parented to init, so the only way to ensure that both
        # die is to target the child process directly.
        if self.root_helper:
            try:
                pid = utils.find_child_pids(pid)[0]
            except IndexError:
                # Process is already dead
                return None
            while True:
                try:
                    # We shouldn't have more than one child per process
                    # so keep getting the children of the first one
                    pid = utils.find_child_pids(pid)[0]
                except IndexError:
                    # Last process in the tree, return it
                    break
        return pid

このメソッドを追っていくと、self.pidの子供の子供をずっとたどっていき、leafの子供を返す。

プロセスの強制終了(_kill_process)::

    def _kill_process(self, pid):
        try:
            # A process started by a root helper will be running as
            # root and need to be killed via the same helper.
            utils.execute(['kill', '-9', pid], root_helper=self.root_helper)
        except Exception as ex:
            stale_pid = (isinstance(ex, RuntimeError) and
                         'No such process' in str(ex))
            if not stale_pid:
                LOG.exception(_('An error occurred while killing [%s].'),
                              self.cmd)
                return False
        return True

このメソッドの例外処理では、killコマンドの結果に"No such process"という文字列が含んでいればFalseで復帰するようになっている。ってことは、OpenStackを実行するときは必ず、LANC=Cで実行する必要があるね。というのと、この種のコードはコマンドに非互換が生じた時に辛い。

プロセスエラーのハンドリング::

    def _handle_process_error(self):
        """Kill the async process and respawn if necessary."""
        LOG.debug(_('Halting async process [%s] in response to an error.'),
                  self.cmd)
        respawning = self.respawn_interval >= 0
        self._kill(respawning=respawning)
        if respawning:
            eventlet.sleep(self.respawn_interval)
            LOG.debug(_('Respawning async process [%s].'), self.cmd)
            self._spawn()

プロセスの監視::

    def _watch_process(self, callback, kill_event):
        while not kill_event.ready():
            try:
                if not callback():
                    break
            except Exception:
                LOG.exception(_('An error occurred while communicating '
                                'with async process [%s].'), self.cmd)
                break
            # Ensure that watching a process with lots of output does
            # not block execution of other greenthreads.
            eventlet.sleep()
        # The kill event not being ready indicates that the loop was
        # broken out of due to an error in the watched process rather
        # than the loop condition being satisfied.
        if not kill_event.ready():
            self._handle_process_error()

第２引数として受け取ったcallbackを実行して、その結果がtrueであれば、_watch_processの処理を続け(callbackをまた呼び出す)、falseであれば_watch_processの最後の処理に移る。if not kill_event...のところでは、kill_eventがまだ発火していなければ、エラーとみなし_handle_process_error()が呼び出される。

ストリームからのリード::

    def _read(self, stream, queue):
        data = stream.readline()
        if data:
            data = data.strip()
            queue.put(data)
            return data

標準出力からの読み込み::

    def _read_stdout(self):
        return self._read(self._process.stdout, self._stdout_lines)

監視対象のプロセスの標準出力から一行読み込み、それをstrip()してから、監視対象プロセスのstdout_linesに書き込む。

標準エラーからの読み込み::

    def _read_stderr(self):
        return self._read(self._process.stderr, self._stderr_lines)

キューのイテレーション::

    def _iter_queue(self, queue):
        while True:
            try:
                yield queue.get_nowait()
            except eventlet.queue.Empty:
                break


標準出力のイテレーション::

    def iter_stdout(self):
        return self._iter_queue(self._stdout_lines)

標準エラーのイテレーション::

    def iter_stderr(self):
        return self._iter_queue(self._stderr_lines)


