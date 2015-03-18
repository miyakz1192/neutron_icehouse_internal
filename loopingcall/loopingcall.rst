========================================
loopingcallの解析
========================================

class LoopingCallBase(object):
---------------------------------

FixedIntervalLoopingCallのベースクラス::

  class LoopingCallBase(object):
      def __init__(self, f=None, *args, **kw):
          self.args = args
          self.kw = kw
          self.f = f
          self._running = False
          self.done = None
  
      def stop(self):
          self._running = False
  
      def wait(self):
          return self.done.wait()
 
__init__で実行する関数と引数を受け取る。

class FixedIntervalLoopingCall(LoopingCallBase):
------------------------------------------------------

pythonのgreenthreadを使った実装。::


  class FixedIntervalLoopingCall(LoopingCallBase):
      """A fixed interval looping call."""
  
      def start(self, interval, initial_delay=None):
          self._running = True
          done = event.Event()
  
          def _inner():
              if initial_delay:
                  greenthread.sleep(initial_delay)
  
              try:
                  while self._running:
                      start = timeutils.utcnow()
                      self.f(*self.args, **self.kw)
                      end = timeutils.utcnow()
                      if not self._running:
                          break
                      delay = interval - timeutils.delta_seconds(start, end)
                      if delay <= 0:
                          LOG.warn(_('task run outlasted interval by %s sec') %
                                   -delay)
                      greenthread.sleep(delay if delay > 0 else 0)
              except LoopingCallDone as e:
                  self.stop()
                  done.send(e.retvalue)
              except Exception:
                  LOG.exception(_('in fixed duration looping call'))
                  done.send_exception(*sys.exc_info())
                  return
              else:
                  done.send(True)
  
          self.done = done
  
          greenthread.spawn_n(_inner)
          return self.done
  

pythonのgreenthreadでは、greenthreadのスレッドはOSのネイティブスレッドと対応するものの、同時に動作するスレッドは１つのみとのこと。
つまり、あるFixedIntervalLoopingCallのスレッドのfがハングアップすると、別のFixedIntervalLoopingCallのスレッドにコンテキストが移らないということになる。

http://d.hatena.ne.jp/mFumi/20140429/1398781151

http://antas.jp/blog/yamakawa/2008/01/python.html
