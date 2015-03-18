==================================================
timeutilsの解析
==================================================

ソース
------

"neutron/openstack/common/timeutils.py" 

このソースを全部追いかけるのは今の時点では、ちょっと無駄なので、
dhcp-agentが使っている部分を中心的に解析を行う。


strtime()
--------------

時刻を文字列にして返却する関数::

  def strtime(at=None, fmt=PERFECT_TIME_FORMAT):
      """Returns formatted utcnow."""
      if not at:
          at = utcnow()
      return at.strftime(fmt)
      
utcnow()
--------------

utc時刻を返す関数::

  def utcnow():
      """Overridable version of utils.utcnow."""
      if utcnow.override_time:
          try:
              return utcnow.override_time.pop(0)
          except AttributeError:
              return utcnow.override_time
      return datetime.datetime.utcnow()

utcnow.override_timeが設定されているようであれば、それを返却し、
そうでなければ、datetimeモジュールのutcnow()を返却する。
  
実際はutcnow.override_timeはNoneに設定されている。
set_time_overrideでアプリケーション側で上書きすることができる。::

  def set_time_override(override_time=None):
      """Overrides utils.utcnow.
  
      Make it return a constant time or a list thereof, one at a time.
  
      :param override_time: datetime instance or list thereof. If not
                            given, defaults to the current UTC time.
      """
      utcnow.override_time = override_time or datetime.datetime.utcnow()
  
