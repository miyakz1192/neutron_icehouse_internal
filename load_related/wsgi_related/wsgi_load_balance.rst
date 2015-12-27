==================================================
eventlet.wsgiは子プロセスにロードバランスするのか
==================================================

調査目的
=========

net-listやcreate_port等、REST APIが呼び出された時、
受け付けたTCP/IPコネクションがどういうアルゴリズムで、各neutron-serverプロセス
に配分されるのかを確認する。

調査(net-listの呼び出し例から)
===================================

net-listを受け付けた時にどのような経路でeventlet.wsgiが呼び出されるか？

結論からいうと、他のtasklet処理がtasklet切り替えが発生する処理を呼び出した時に
eventletのスケジューラが動作して、tasklet切り替えが起こり、
eventlet.wsgiが呼び出されることがわかった。1つのプロセスの中でeventletのスケジューラによって
様々な処理が切り替えながら実行されている。REST APIの受付処理はクライアントから要求を
受信しても即座に実行されるわけではなく、他のtaskletの処理の延長で
スケジューラが呼び出された際に、切り替えが行われる。
そのため、大量の処理が並列して実行されている場合は、いつまで経っても
目的の処理が実行されない場合がある。

また、大量のリクエストが来たとしても、各api_workerに等しく要求が分散される
かどうかは不明である。

以下、内容詳細。::

  (snip)

  4777773 impl_kombu.py(164):             message.ack()  ★ AMQP関連の ack処理が呼び出される
  4777774  --- modulename: message, funcname: ack
  4777775 message.py(57):         if self.channel.no_ack_consumers is not None:
  4777776 message.py(58):             try:
  4777777 message.py(59):                 consumer_tag = self.delivery_info['consumer_tag']
  4777778 message.py(63):                 if consumer_tag in self.channel.no_ack_consumers:
  4777779 message.py(65):         if self.acknowledged:
  4777780  --- modulename: message, funcname: acknowledged
  4777781 message.py(128):         return self._state in ACK_STATES
  4777782 message.py(69):         self.channel.basic_ack(self.delivery_tag)
  4777783  --- modulename: channel, funcname: basic_ack
  4777784 channel.py(1572):         args = AMQPWriter()
  4777785  --- modulename: serialization, funcname: __init__
  4777786 serialization.py(210):         self.out = BytesIO() if dest is None else dest
  4777787 serialization.py(211):         self.bits = []
  4777788 serialization.py(212):         self.bitcount = 0
  4777789 channel.py(1573):         args.write_longlong(delivery_tag)
  4777790  --- modulename: serialization, funcname: write_longlong
  4777791 serialization.py(282):         if n < 0 or n >= 18446744073709551616:
  4777792 serialil.py(94):         for fileno, event in presult:
  4777793 poll.py(112):         if self.debug_blocking:

  このpoll.py(112)周辺は以下のコード。

  112         if self.debug_blocking:
  113             self.block_detect_post()

  self.block_detect_postは以下

  99     def block_detect_post(self):
  100         if (hasattr(self, "_old_signal_handler") and
  101             self._old_signal_handler):
  102             signal.signal(signal.SIGALRM, self._old_signal_handler)
  103         signal.alarm(0)

  signal.alarm(0)で、おそらく、以下のメソッドが呼び出される。
  おそらく、eventletのスケジューラのコアコード。
  AMQP関連の処理がブロックしたらしく、その終了のタイミングでこれが呼ばれた
  と考える。
  
  215     def run(self, *a, **kw):
  216         """Run the runloop until abort is called.
  217         """
  218         # accept and discard variable arguments because they will be
  219         # supplied if other greenlets have run and exited before the
  220         # hub's greenlet gets a chance to run
  221         if self.running:
  222             raise RuntimeError("Already running!")
  223         try:
  224             self.running = True
  225             self.stopping = False
  226             while not self.stopping:

  4777794 hub.py(226):             while not self.stopping:
  4777795 hub.py(227):                 self.prepare_timers()
  4777796  --- modulename: hub, funcname: prepare_timers
  4777797 hub.py(297):         heappush = heapq.heappush
  4777798 hub.py(298):         t = self.timers
  4777799 hub.py(299):         for item in self.next_timers:
  4777800 hub.py(300):             if item[1].called:
  4777801 hub.py(303):                 heappush(t, item)
  4777802 hub.py(299):         for item in self.next_timers:
  4777803 hub.py(304):         del self.next_timers[:]
  4777804 hub.py(228):                 if self.debug_blocking:
  4777805 hub.py(230):                 self.fire_timers(self.clock())
  4777806  --- modulename: hub, funcname: fire_timers
  4777807 hub.py(332):         t = self.timers
  4777808 hub.py(333):         heappop = heapq.heappop
  4777809 hub.py(335):         while t:
  4777810 hub.py(336):             next = t[0]
  4777811 hub.py(338):             exp = next[0]
  4777812 hub.py(339):             timer = next[1]
  4777813 hub.py(341):             if when < exp:
  4777814 hub.py(344):             heappop(t)
  4777815 hub.py(346):             try:
  4777816 hub.py(347):                 if timer.called:
  4777817 hub.py(350):                     timer()

  (snip)

  4777818  --- modulename: timer, funcname: __call__
  4777819 timer.py(52):         if not self.called:
  4777820 timer.py(53):             self.called = True
  4777821 timer.py(54):             cb, args, kw = self.tpl
  4777822 timer.py(55):             try:
  4777823 timer.py(56):                 cb(*args, **kw)

  cbがおそらく、_spawn_n_implである。

  (snip)

  4777824  --- modulename: greenpool, funcname: _spawn_n_impl　★　create_portのbt実行時に最初に現れるメソッドがこれ！
  4777825 greenpool.py(78):         try:
  4777826 greenpool.py(79):             try:
  4777827 greenpool.py(80):                 func(*args, **kwargs)

  funcはおそらく、process_requestである。
  スケジューラの処理の結果、REST APIの受付処理である、process_requestの処理の
  実行が選択された。

  (snip)

  4777828  --- modulename: wsgi, funcname: process_request
  4777829 wsgi.py(595):     def process_request(self, (socket, address)):
  4777830 wsgi.py(599):         proto = types.InstanceType(self.protocol)
  4777831 wsgi.py(600):         if self.minimum_chunk_size is not None:
  4777832 wsgi.py(602):         proto.__init__(socket, address, self)
  4777833  --- modulename: SocketServer, funcname: __init__
  4777834 SocketServer.py(644):         self.request = request
  4777835 SocketServer.py(645):         self.client_address = client_address
  4777836 SocketServer.py(646):         self.server = server
  4777837 SocketServer.py(647):         self.setup()
  4777838  --- modulename: wsgi, funcname: setup
  4777839 wsgi.py(208):         conn = self.connection = self.request
  4777840 wsgi.py(209):         try:
  4777841 wsgi.py(210):             self.rfile = conn.makefile('rb', self.rbufsize)
  4777842  --- modulename: greenio, funcname: makefile
  4777843 greenio.py(238):         return _fileobject(self.dup(), *args, **kw)
  4777844  --- modulename: greenio, funcname: dup
  4777845 greenio.py(232):         sock = self.fd.dup(*args, **kw)
  4777846  --- modulename: socket, funcname: dup
  4777847 socket.py(210):         return _socketobject(_sock=self._sock)
  4777848  --- modulename: socket, funcname: __init__

  (snip)

  4777988 socket.py(270):         self._close = close
  4777989 wsgi.py(211):             self.wfile = conn.makefile('wb', self.wbufsize)
  4777990  --- modulename: greenio, funcname: makefile
  4777991 greenio.py(238):         return _fileobject(self.dup(), *args, **kw)
  4777992  --- modulename: greenio, funcname: dup
  4777993 greenio.py(232):         sock = self.fd.dup(*args, **kw)
  4777994  --- modulename: socket, funcname: dup
  4777995 socket.py(210):         return _socketobject(_sock=self._sock)
  4777996  --- modulename: socket, funcname: __init__

  (snip)

  4778023 connection.py(778):         if self._transport is None:

  (snip)

  4778050 connection.py(331):             method_queue = channel.method_queue

  (snip)

  4778060  --- modulename: connection, funcname: read_timeout

  (snip)

  4778072  --- modulename: transport, funcname: read_frame

  (snip)

  4778097 greenio.py(139):         if should_set_nonblocking:

  (snip)

  4778113 greenio.py(326):             self.setblocking(True)
  4778114  --- modulename: greenio, funcname: setblocking
  ※  setblockingをTrueに設定してブロッキングモードにしている。
  
  (snip)

  4778120  --- modulename: socket, funcname: __init__
  4778121 socket.py(247):         self._sock = sock

  (snip)

  4778133 SocketServer.py(648):         try:
  4778134 SocketServer.py(649):             self.handle()
  4778135  --- modulename: BaseHTTPServer, funcname: handle
  4778136 BaseHTTPServer.py(338):         self.close_connection = 1
  4778137 BaseHTTPServer.py(340):         self.handle_one_request()

  (snip)

  4781582 common.py(270):   2015-12-26 14:04:17.251 10687 INFO neutron.wsgi [-] WSGI_REQ_START: 192.168.122.84 - - [26/Dec/2015 14:04:17] "GET /v2.0/networks.json HTTP/1.1" 80d0cdf8-87ce-4f60-b572-7f569d0d0a71

  ここでやっと、REST APIの受付開始が始まる。以下のコード( as is から改造. wsgi.py)::

  222     def handle_one_request(self): 
  223         if self.server.max_http_version:                                        
  224             self.protocol_version = self.server.max_http_version                
  225                                                                                 
  226         if self.rfile.closed:                                                   
  227             self.close_connection = 1                                           
  228             return  
  (snip)
  393                 if self.server.log_output:                                      
  394                     self.server.log_message(DEFAULT_LOG_FORMAT_START % { 
  395                         'client_ip': self.get_client_ip(),                      
  396                         'client_port': self.client_address[1],                  
  397                         'date_time': self.log_date_time_string(),               
  398                         'request_line': self.requestline,                       
  399                         'uuid':         uuid_str                                
  400                     })   

以下、eventletスケジューラの調査を行う。

hub.pyの調査
============

hub.pyのrunメソッドがeventletのスケジューラのコアであることは間違い
なさそうだ。ここの仕組みを抑えることで、eventletを使ったneutronの
パフォーマンスの何が問題かが見えてきそうだ。先のnet-listの例だと、
以下のように、fire_timersで次の実行対象処理を選択しているように見える。::


  4777794 hub.py(226):             while not self.stopping:
  4777795 hub.py(227):                 self.prepare_timers()
  4777796  --- modulename: hub, funcname: prepare_timers
  4777797 hub.py(297):         heappush = heapq.heappush
  4777798 hub.py(298):         t = self.timers
  4777799 hub.py(299):         for item in self.next_timers:
  4777800 hub.py(300):             if item[1].called:
  4777801 hub.py(303):                 heappush(t, item)
  4777802 hub.py(299):         for item in self.next_timers:
  4777803 hub.py(304):         del self.next_timers[:]
  4777804 hub.py(228):                 if self.debug_blocking:
  guel4777805 hub.py(230):                 self.fire_timers(self.clock())
  4777806  --- modulename: hub, funcname: fire_timers
  4777807 hub.py(332):         t = self.timers
  4777808 hub.py(333):         heappop = heapq.heappop
  4777809 hub.py(335):         while t:
  4777810 hub.py(336):             next = t[0]
  4777811 hub.py(338):             exp = next[0]
  4777812 hub.py(339):             timer = next[1]
  4777813 hub.py(341):             if when < exp:
  4777814 hub.py(344):             heappop(t)
  4777815 hub.py(346):             try:
  4777816 hub.py(347):                 if timer.called:
  4777817 hub.py(350):                     timer()
  4777794 hub.py(226):             while not self.stopping:
  4777795 hub.py(227):                 self.prepare_timers()
  4777796  --- modulename: hub, funcname: prepare_timers
  4777797 hub.py(297):         heappush = heapq.heappush
  4777798 hub.py(298):         t = self.timers
  4777799 hub.py(299):         for item in self.next_timers:
  4777800 hub.py(300):             if item[1].called:
  4777801 hub.py(303):                 heappush(t, item)
  4777802 hub.py(299):         for item in self.next_timers:
  4777803 hub.py(304):         del self.next_timers[:]
  4777804 hub.py(228):                 if self.debug_blocking:
  4777805 hub.py(230):                 self.fire_timers(self.clock())
  4777806  --- modulename: hub, funcname: fire_timers
  4777807 hub.py(332):         t = self.timers
  4777808 hub.py(333):         heappop = heapq.heappop
  4777809 hub.py(335):         while t:
  4777810 hub.py(336):             next = t[0]
  4777811 hub.py(338):             exp = next[0]
  4777812 hub.py(339):             timer = next[1]
  4777813 hub.py(341):             if when < exp:
  4777814 hub.py(344):             heappop(t)
  4777815 hub.py(346):             try:
  4777816 hub.py(347):                 if timer.called:
  4777817 hub.py(350):                     timer()

ここで、fire_timers実行時のself.timersが次に実行すべきタスクのように見える。
ためしに、self.timersを分析してみる::

  self.timers自体はタプルの配列。

  (Pdb) p self.timers
  [(1451200697.444856, Timer(0, None, *None, **None))]
  (Pdb) 
  (Pdb) p self.timers[0]
  (1451200697.444856, Timer(0, None, *None, **None))
  (Pdb) 

  Timerを分析してみると、以下。greenlet.greenletのswitchメソッドが登録されている。
  0秒後に実行するように設定されている

  (Pdb) self.timers[0][1]
  Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})
  (Pdb) inspect.getmembers(self.timers[0][1])
  [('__call__', <bound method Timer.__call__ of Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})>), ('__class__', <class 'eventlet.hubs.timer.Timer'>), ('__delattr__', <method-wrapper '__delattr__' of Timer object at 0x7f3634050850>), ('__dict__', {'seconds': 0, 'tpl': (<built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, (), {}), 'called': False}), ('__doc__', None), ('__format__', <built-in method __format__ of Timer object at 0x7f3634050850>), ('__getattribute__', <method-wrapper '__getattribute__' of Timer object at 0x7f3634050850>), ('__hash__', <method-wrapper '__hash__' of Timer object at 0x7f3634050850>), ('__init__', <bound method Timer.__init__ of Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})>), ('__lt__', <bound method Timer.__lt__ of Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})>), ('__module__', 'eventlet.hubs.timer'), ('__new__', <built-in method __new__ of type object at 0x9175e0>), ('__reduce__', <built-in method __reduce__ of Timer object at 0x7f3634050850>), ('__reduce_ex__', <built-in method __reduce_ex__ of Timer object at 0x7f3634050850>), ('__repr__', <bound method Timer.__repr__ of Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})>), ('__setattr__', <method-wrapper '__setattr__' of Timer object at 0x7f3634050850>), ('__sizeof__', <built-in method __sizeof__ of Timer object at 0x7f3634050850>), ('__str__', <method-wrapper '__str__' of Timer object at 0x7f3634050850>), ('__subclasshook__', <built-in method __subclasshook__ of type object at 0x1900c00>), ('__weakref__', None), ('called', False), ('cancel', <bound method Timer.cancel of Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})>), ('copy', <bound method Timer.copy of Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})>), ('pending', True), ('schedule', <bound method Timer.schedule of Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, *(), **{})>), ('seconds', 0), ('tpl', (<built-in method switch of greenlet.greenlet object at 0x7f3638e207d0>, (), {}))]

  いろいろ調べてみるが、Timerはどれでもない。


  (Pdb) inspect.isclass(self.timers[0][1])
  False
  (Pdb) inspect.ismethod(self.timers[0][1])
  False
  (Pdb) inspect.isfunction(self.timers[0][1])
  False
  (Pdb) inspect.isgenerator(self.timers[0][1])
  False
  (Pdb) inspect.isgeneratorfunction(self.timers[0][1])
  False
  (Pdb) inspect.isframe(self.timers[0][1])
  False
  (Pdb) inspect.iscode(self.timers[0][1])
  False
  (Pdb) inspect.isbuiltin(self.timers[0][1])
  False
  (Pdb) inspect.isroutine(self.timers[0][1])
  False
  (Pdb) inspect.isabstract(self.timers[0][1])
  False
  (Pdb) inspect.ismethoddescriptor(self.timers[0][1])
  False
  (Pdb) p self.timers[0][1].called
  False

  試しに実行してみると、次の処理が実行されるみたいだ。

  (Pdb) p self.timers[0][1]()
  2015-12-27 16:34:41.157 4391 INFO neutron.plugins.ml2.managers [-] Initializing driver for type 'vlan'

  ※  これはself.timesのtimerが以下の値の場合だった。
  [(1451202351.00831, Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f9228c127d0>, *(), **{}))]

  None
  (Pdb) p self.timers[0][1]()
  None
  (Pdb) p self.timers[0][1].called
  True
  (Pdb) 

  fire_timersを見ると以下

  331     def fire_timers(self, when):                                                
  332         import pdb                                                              
  333         pdb.set_trace()                                                         
  334         t = self.timers                                                         
  335         heappop = heapq.heappop  ★  heapqのheappopメソッドをheappopとして抽出
  336                                                                                 
  337         while t:                                                                
  338             next = t[0]                                                         
  339                                                                                 
 
  ここで、上記タプルのうち、expとtimer部にわけて取得::

  340             exp = next[0]                                                       
  341             timer = next[1]                                                     
  342                                                                                 
  343             if when < exp:                                                      
  344                 break                                                           
  345                                                                                 

  self.timersから要素をpopする。以下のように要素が常に一つしかないため、
  実行結果は常に同じなようだ。
  [(1451202351.00831, Timer(0, <built-in method switch of greenlet.greenlet object at 0x7f9228c127d0>, *(), **{}))]
  
  346             heappop(t)                                                          
  347                                                                                 
  348             try:                                                                
  349                 if timer.called:                                                
  350                     self.timers_canceled -= 1                                   
  351                 else:                                                           
  352                     timer()  ★  ここで処理を実行
  353             except self.SYSTEM_EXCEPTIONS:                                      
  354                 raise                                                           
  355             except:                                                             
  356                 self.squelch_timer_exception(timer, sys.exc_info())             
  357                 clear_sys_exc_info()   


  呼び出し元のrunに戻る。runこそがeventletのスケジューラの心臓部である。

  215     def run(self, *a, **kw):
  216         """Run the runloop until abort is called.                               
  217         """                                                                     
  218         # accept and discard variable arguments because they will be            
  219         # supplied if other greenlets have run and exited before the            
  220         # hub's greenlet gets a chance to run                                   
  221         if self.running:                                                        
  222             raise RuntimeError("Already running!")                              
  223         try:                                                                    
  224             self.running = True                                                 
  225             self.stopping = False                                               
  226             while not self.stopping:                                            
  227                 self.prepare_timers()                                           
  228                 if self.debug_blocking:                                         
  229                     self.block_detect_pre()                                     

  self.timersに登録されているswitchメソッドが定期的に呼び出される。
  プログラムがstopするまで延々と実行される。

  230                 self.fire_timers(self.clock())                                  
  231                 if self.debug_blocking:                                         
  232                     self.block_detect_post()                                    
  233                 self.prepare_timers()                                           
  234                 wakeup_when = self.sleep_until()                                
  235                 if wakeup_when is None:                                         
  236                     sleep_time = self.default_sleep()                           
  237                 else:                                                           
  238                     sleep_time = wakeup_when - self.clock()                     
  239                 if sleep_time > 0:                                              
  240                     self.wait(sleep_time)                                       
  241                 else:                                                           
  242                     self.wait(0)                                                
  243             else:                                                               
  244                 self.timers_canceled = 0                                        
  245                 del self.timers[:]                                              
  246                 del self.next_timers[:]                                         
  247         finally:                                                                
  248             self.running = False                                                
  249             self.stopping = False  

  では、switchメソッドはどうなっているのか。

  171     def switch(self):                                                           
  172         cur = greenlet.getcurrent()                                             
  173         assert cur is not self.greenlet, 'Cannot switch to MAINLOOP from MAINLOOP'
  174         switch_out = getattr(cur, 'switch_out', None)                           
  175 #        import pdb                                                             
  176 #        pdb.set_trace()                                                        
  177 #        import inspect                                                         
  178                                                                                 
  179         if switch_out is not None:                                              
  180             try:                                                                
  181                 switch_out()                                                    
  182             except:                                                             
  183                 self.squelch_generic_exception(sys.exc_info())                  
  184         self.ensure_greenlet()                                                  
  185         try:                                                                    
  186             if self.greenlet.parent is not cur:                                 
  187                 cur.parent = self.greenlet                                      
  188         except ValueError:                                                      
  189             pass  # gets raised if there is a greenlet parent cycle             
  190         clear_sys_exc_info()                                                    
  191         return self.greenlet.switch()      

  ちなみに、clear_sys_exc_infoは何もしないメソッドである。

  (Pdb) n
  > /usr/lib/python2.7/dist-packages/eventlet/support/__init__.py(32)clear_sys_exc_info()
  -> pass
  (Pdb) l
   27   else:
   28       def clear_sys_exc_info():
   29           """No-op In py3k. 
   30           Exception information is not visible outside of except statements.
   31           sys.exc_clear became obsolete and removed."""
   32  ->         pass

  ここで、改めて処理の解析を見直すために、ある回のswitchの呼び出しを見てみる。
  最後のself.greenlet.switch()(L191)が呼び出されると、greenthread.pyのsleepに戻る

  (Pdb) s
  --Return--
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(191)switch()->()
  -> return self.greenlet.switch()
  (Pdb) s
  > /usr/lib/python2.7/dist-packages/eventlet/greenthread.py(33)sleep()
  -> timer.cancel()
  (Pdb) l
   28       assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
   29       timer = hub.schedule_call_global(seconds, current.switch)
   30       try:
   31           hub.switch()
   32       finally:
   33  ->         timer.cancel()
   34           
   35   
   36   def spawn(func, *args, **kwargs):
   37       """Create a greenthread to run ``func(*args, **kwargs)``.  Returns a 
   38       :class:`GreenThread` object which you can use to get the results of the 
  (Pdb) s
  --Call--
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/timer.py(63)cancel()
  -> def cancel(self):
  (Pdb) l
   58                   try:
   59                       del self.tpl
   60                   except AttributeError:
   61                       pass
   62   
   63  ->     def cancel(self):
   64           """Prevent this timer from being called. If the timer has already
   65           been called or canceled, has no effect.
   66           """
   67           if not self.called:
   68               self.called = True
  (Pdb) n
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/timer.py(67)cancel()
  -> if not self.called:
  (Pdb) l
   62   
   63       def cancel(self):
   64           """Prevent this timer from being called. If the timer has already
   65           been called or canceled, has no effect.
   66           """
   67  ->         if not self.called:
   68               self.called = True
   69               get_hub().timer_canceled(self)
   70               try:
   71                   del self.tpl
   72               except AttributeError:
  (Pdb) n
  --Return--
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/timer.py(67)cancel()->None
  -> if not self.called:
  (Pdb) l
   62   
   63       def cancel(self):
   64           """Prevent this timer from being called. If the timer has already
   65           been called or canceled, has no effect.
   66           """
   67  ->         if not self.called:
   68               self.called = True
   69               get_hub().timer_canceled(self)
   70               try:
   71                   del self.tpl
   72               except AttributeError:
  (Pdb) n
  --Return--
  > /usr/lib/python2.7/dist-packages/eventlet/greenthread.py(33)sleep()->None
  -> timer.cancel()
  (Pdb) l
   28       assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
   29       timer = hub.schedule_call_global(seconds, current.switch)
   30       try:
   31           hub.switch()
   32       finally:
   33  ->         timer.cancel()
   34           
   35   
   36   def spawn(func, *args, **kwargs):
   37       """Create a greenthread to run ``func(*args, **kwargs)``.  Returns a 
   38       :class:`GreenThread` object which you can use to get the results of the 
  (Pdb) s

  switchのもともとの呼び出し元である、sqlalchemyのsession.pyに戻る。

  --Return--
  > /opt/stack/neutron/neutron/openstack/common/db/sqlalchemy/session.py(669)_thread_yield()->None
  -> time.sleep(0)
  (Pdb) l
  664       execute instead of time.sleep(0).
  665       Force a context switch. With common database backends (eg MySQLdb and
  666       sqlite), there is no implicit yield caused by network I/O since they are
  667       implemented by C libraries that eventlet cannot monkey patch.
  668       """
  669  ->     time.sleep(0)

  hubのrunやfire_timersはself.timersに登録された処理をひたすら実行するだけである。
  schedule_call_globalが呼び出されると、その中で実行されるadd_timerにより、
  self.next_timersに処理が登録されるようだ。prepare_timersメソッドは、
  self.next_timersから、self.timersに登録されたメソッドを移動する。
  そして、runにより実行されるわけだ。
  つまり、eventletの処理がどのようにスケジュールされるかは、schedule_call_local
  の呼び出し元を追えばよい。
  例えば、以下である.

  一つ目。

     /opt/stack/neutron/neutron/openstack/common/db/sqlalchemy/session.py(669)_thread_yield()
   -> time.sleep(0)
     /usr/lib/python2.7/dist-packages/eventlet/greenthread.py(29)sleep()
   -> timer = hub.schedule_call_global(seconds, current.switch)
   > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(331)schedule_call_global()
   -> t = timer.Timer(seconds, cb, *args, **kw)
   (Pdb) 

   二つ目。

    /usr/lib/python2.7/dist-packages/kombu/transport/pyamqp.py(111)establish_connection()
  -> conn = self.Connection(**opts)
    /usr/lib/python2.7/dist-packages/amqp/connection.py(148)__init__()
  -> self.transport = create_transport(host, connect_timeout, ssl)
    /usr/lib/python2.7/dist-packages/amqp/transport.py(300)create_transport()
  -> return TCPTransport(host, connect_timeout)
    /usr/lib/python2.7/dist-packages/amqp/transport.py(98)__init__()
  -> self.sock.connect(sa)
    /usr/lib/python2.7/dist-packages/eventlet/greenio.py(203)connect()
  -> timeout_exc=socket.timeout("timed out"))
    /usr/lib/python2.7/dist-packages/eventlet/hubs/__init__.py(148)trampoline()
  -> t = hub.schedule_call_global(timeout, current.throw, timeout_exc)
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(331)schedule_call_global()
  -> t = timer.Timer(seconds, cb, *args, **kw)
  (Pdb) 

  三つ目。

    /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py(177)consume_in_thread()
  -> return self.connection.consume_in_thread()
    /opt/stack/neutron/neutron/openstack/common/rpc/impl_kombu.py(750)consume_in_thread()
  -> self.consumer_thread = eventlet.spawn(_consumer_thread)
    /usr/lib/python2.7/dist-packages/eventlet/greenthread.py(48)spawn()
  -> hub.schedule_call_global(0, g.switch, func, args, kwargs)
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(331)schedule_call_global()
  -> t = timer.Timer(seconds, cb, *args, **kw)
  (Pdb) 


それぞれについて、分析をすすめる。

一つ目
========

コードとしては以下。::

  /opt/stack/neutron/neutron/openstack/common/db/sqlalchemy/session.py(669)_thread_yield()
  -> time.sleep(0)
    /usr/lib/python2.7/dist-packages/eventlet/greenthread.py(29)sleep()
  -> timer = hub.schedule_call_global(seconds, current.switch)
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(331)schedule_call_global()
  -> t = timer.Timer(seconds, cb, *args, **kw)
  (Pdb) 

コードとしては以下。::

   15 def sleep(seconds=0):                                                           
   16     """Yield control to another eligible coroutine until at least *seconds* have
   17     elapsed.                                                                    
   18                                                                                 
   19     *seconds* may be specified as an integer, or a float if fractional seconds  
   20     are desired. Calling :func:`~greenthread.sleep` with *seconds* of 0 is the  
   21     canonical way of expressing a cooperative yield. For example, if one is     
   22     looping over a large list performing an expensive calculation without       
   23     calling any socket methods, it's a good idea to call ``sleep(0)``           
   24     occasionally; otherwise nothing else will run.                              
   25     """                                                                         
   26     hub = hubs.get_hub()                                                        
   27     current = getcurrent()                                                      
   28     assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
   29     timer = hub.schedule_call_global(seconds, current.switch)                                                                                   
   30     try:                                                                        
   31         hub.switch()                                                            
   32     finally:                                                                    
   33         timer.cancel() 

sleepが呼び出されると、current.switchがtimersに登録される形になる。 

二つ目
========

コードとしては以下。::

  /usr/lib/python2.7/dist-packages/kombu/transport/pyamqp.py(111)establish_connection()
  -> conn = self.Connection(**opts)
    /usr/lib/python2.7/dist-packages/amqp/connection.py(148)__init__()
  -> self.transport = create_transport(host, connect_timeout, ssl)
    /usr/lib/python2.7/dist-packages/amqp/transport.py(300)create_transport()
  -> return TCPTransport(host, connect_timeout)
    /usr/lib/python2.7/dist-packages/amqp/transport.py(98)__init__()
  -> self.sock.connect(sa)
    /usr/lib/python2.7/dist-packages/eventlet/greenio.py(203)connect()
  -> timeout_exc=socket.timeout("timed out"))
    /usr/lib/python2.7/dist-packages/eventlet/hubs/__init__.py(148)trampoline()
  -> t = hub.schedule_call_global(timeout, current.throw, timeout_exc)
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(331)schedule_call_global()
  -> t = timer.Timer(seconds, cb, *args, **kw)
  (Pdb) 

  trampolineのコードは以下。

  121 def trampoline(fd, read=None, write=None, timeout=None,                         
  122                timeout_exc=timeout.Timeout):                                    
  123     """Suspend the current coroutine until the given socket object or file      
  124     descriptor is ready to *read*, ready to *write*, or the specified           
  125     *timeout* elapses, depending on arguments specified.                        
  126                                                                                 
  127     To wait for *fd* to be ready to read, pass *read* ``=True``; ready to       
  128     write, pass *write* ``=True``. To specify a timeout, pass the *timeout*     
  129     argument in seconds.                                                        
  130                                                                                 
  131     If the specified *timeout* elapses before the socket is ready to read or    
  132     write, *timeout_exc* will be raised instead of ``trampoline()``             
  133     returning normally.                                                         
  134                                                                                 
  135     .. note :: |internal|                                                       
  136     """      
  137     t = None                                                                    
  138     hub = get_hub()                                                             
  139     current = greenlet.getcurrent()                                             
  140     assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
  141     assert not (                                                                
  142         read and write), 'not allowed to trampoline for reading and writing'    
  143     try:                                                                        
  144         fileno = fd.fileno()                                                    
  145     except AttributeError:                                                      
  146         fileno = fd                                                             
  147     if timeout is not None:                                                     
  148         t = hub.schedule_call_global(timeout, current.throw, timeout_exc)       
  149     try:                                                                        
  150         if read:                                                                
  151             listener = hub.add(hub.READ, fileno, current.switch)                
  152         elif write:                                                             
  153             listener = hub.add(hub.WRITE, fileno, current.switch)               
  154         try:                                                                    
  155             return hub.switch()                                                 
  156         finally:                                                                
  157             hub.remove(listener)                                                
  158     finally:                                                                    
  159         if t is not None:                                                       
  160             t.cancel()   

  greenlet.getcurrent()のswitchが登録される。

三つ目
========

コードとしては以下。::

  /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py(177)consume_in_thread()
  -> return self.connection.consume_in_thread()
    /opt/stack/neutron/neutron/openstack/common/rpc/impl_kombu.py(750)consume_in_thread()
  -> self.consumer_thread = eventlet.spawn(_consumer_thread)
    /usr/lib/python2.7/dist-packages/eventlet/greenthread.py(48)spawn()
  -> hub.schedule_call_global(0, g.switch, func, args, kwargs)
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(331)schedule_call_global()
  -> t = timer.Timer(seconds, cb, *args, **kw)
  (Pdb) 

spawnのコードは以下。::

  36 def spawn(func, *args, **kwargs):                                               
  37     """Create a greenthread to run ``func(*args, **kwargs)``.  Returns a        
  38     :class:`GreenThread` object which you can use to get the results of the     
  39     call.                                                                       
  40                                                                                 
  41     Execution control returns immediately to the caller; the created greenthread
  42     is merely scheduled to be run at the next available opportunity.            
  43     Use :func:`spawn_after` to  arrange for greenthreads to be spawned          
  44     after a finite delay.                                                       
  45     """                                                                         
  46     hub = hubs.get_hub()                                                        
  47     g = GreenThread(hub.greenlet)                                               
  48     hub.schedule_call_global(0, g.switch, func, args, kwargs)                   
  49     return g   

GreenThreadのインスタンスが登録される。

schedule_call_global以下の実装
================================

コードとしては以下。::

  320     def schedule_call_global(self, seconds, cb, *args, **kw):                   
  321         """Schedule a callable to be called after 'seconds' seconds have        
  322         elapsed. The timer will NOT be canceled if the current greenlet has     
  323         exited before the timer fires.                                          
  324             seconds: The number of seconds to wait.                             
  325             cb: The callable to call after the given time.                      
  326             *args: Arguments to pass to the callable when called.               
  327             **kw: Keyword arguments to pass to the callable when called.        
  328         """                                                                     
  329 #        import pdb                                                             
  330 #        pdb.set_trace()                                                        
  331         t = timer.Timer(seconds, cb, *args, **kw)                                                                                               
  332         self.add_timer(t)                                                       
  333         return t   

add_timerの実装は以下。::

  282     def add_timer(self, timer): 
  283         scheduled_time = self.clock() + timer.seconds                           
  284         self.next_timers.append((scheduled_time, timer))                        
  285         return scheduled_time     

何も考えずにnext_timers(=timers)に登録される。
prepare_timersも何も考えていない。::

  296     def prepare_timers(self):
  297         heappush = heapq.heappush                                               
  298         t = self.timers                                                         
  299         for item in self.next_timers:                                           
  300             if item[1].called:                                                  
  301                 self.timers_canceled -= 1                                       
  302             else:                                                               
  303                 heappush(t, item)                                               
  304         del self.next_timers[:]  

runも単にself.timersを引っ張ってきているだけ。::

  215     def run(self, *a, **kw):                                                    
  216         """Run the runloop until abort is called.                               
  217         """                                                                     
  218         # accept and discard variable arguments because they will be            
  219         # supplied if other greenlets have run and exited before the            
  220         # hub's greenlet gets a chance to run                                   
  221         if self.running:                                                        
  222             raise RuntimeError("Already running!")                              
  223         try:                                                                    
  224             self.running = True                                                 
  225             self.stopping = False                                               
  226             while not self.stopping:                                            
  227                 self.prepare_timers()                                           
  228                 if self.debug_blocking:                                         
  229                     self.block_detect_pre()                                     
  230                 self.fire_timers(self.clock())                                  
  231                 if self.debug_blocking:                                         
  232                     self.block_detect_post()                                    
  233                 self.prepare_timers()                                           
  234                 wakeup_when = self.sleep_until()                                
  235                 if wakeup_when is None:                                         
  236                     sleep_time = self.default_sleep()                           
  237                 else:                                                           
  238                     sleep_time = wakeup_when - self.clock()                     
  239                 if sleep_time > 0:                                              
  240                     self.wait(sleep_time)                                       
  241                 else:                                                           
  242                     self.wait(0)                                                
  243             else:                                                               
  244                 self.timers_canceled = 0                                        
  245                 del self.timers[:]                                              
  246                 del self.next_timers[:]                                         
  247         finally:                                                                
  248             self.running = False                                                
  249             self.stopping = False   

要するにeventletのスケジューラは、非常に単純で、sleepやconnect、spawnなどが実行された
タイミングで、それを呼び出した処理が、timersに登録される。
そして、過去に登録された処理が、登録された順で呼び出されることがわかった。

参考
=====

switchメソッドが呼ばれる経路の一つ。
sqlの呼び出しの前にthread yieldが呼び出されている。::

  (Pdb) bt
    /usr/local/bin/neutron-server(9)<module>()
  -> load_entry_point('neutron==2014.1.4.dev76', 'console_scripts', 'neutron-server')()
    /opt/stack/neutron/neutron/server/__init__.py(48)main()
  -> neutron_api = service.serve_wsgi(service.NeutronApiService)
    /opt/stack/neutron/neutron/service.py(105)serve_wsgi()
  -> service.start()
    /opt/stack/neutron/neutron/service.py(74)start()
  -> self.wsgi_app = _run_wsgi(self.app_name)
    /opt/stack/neutron/neutron/service.py(173)_run_wsgi()
  -> app = config.load_paste_app(app_name)
    /opt/stack/neutron/neutron/common/config.py(170)load_paste_app()
  -> app = deploy.loadapp("config:%s" % config_path, name=app_name)
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(247)loadapp()
  -> return loadobj(APP, uri, name=name, **kw)
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(272)loadobj()
  -> return context.create()
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(710)create()
  -> return self.object_type.invoke(self)
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(144)invoke()
  -> **context.local_conf)
    /usr/lib/python2.7/dist-packages/paste/deploy/util.py(55)fix_call()
  -> val = callable(*args, **kw)
    /usr/lib/python2.7/dist-packages/paste/urlmap.py(28)urlmap_factory()
  -> app = loader.get_app(app_name, global_conf=global_conf)
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(350)get_app()
  -> name=name, global_conf=global_conf).create()
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(710)create()
  -> return self.object_type.invoke(self)
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(144)invoke()
  -> **context.local_conf)
    /usr/lib/python2.7/dist-packages/paste/deploy/util.py(55)fix_call()
  -> val = callable(*args, **kw)
    /opt/stack/neutron/neutron/auth.py(69)pipeline_factory()
  -> app = loader.get_app(pipeline[-1])
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(350)get_app()
  -> name=name, global_conf=global_conf).create()
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(710)create()
  -> return self.object_type.invoke(self)
    /usr/lib/python2.7/dist-packages/paste/deploy/loadwsgi.py(146)invoke()
  -> return fix_call(context.object, context.global_conf, **context.local_conf)
    /usr/lib/python2.7/dist-packages/paste/deploy/util.py(55)fix_call()
  -> val = callable(*args, **kw)
    /opt/stack/neutron/neutron/api/v2/router.py(72)factory()
  -> return cls(**local_config)
    /opt/stack/neutron/neutron/api/v2/router.py(76)__init__()
  -> plugin = manager.NeutronManager.get_plugin()
    /opt/stack/neutron/neutron/manager.py(222)get_plugin()
  -> return weakref.proxy(cls.get_instance().plugin)
    /opt/stack/neutron/neutron/manager.py(216)get_instance()
  -> cls._create_instance()
    /opt/stack/neutron/neutron/openstack/common/lockutils.py(249)inner()
  -> return f(*args, **kwargs)
    /opt/stack/neutron/neutron/manager.py(202)_create_instance()
  -> cls._instance = cls()
    /opt/stack/neutron/neutron/manager.py(114)__init__()
  -> plugin_provider)
    /opt/stack/neutron/neutron/manager.py(142)_get_plugin_instance()
  -> return plugin_class()
    /opt/stack/neutron/neutron/plugins/ml2/plugin.py(108)__init__()
  -> super(Ml2Plugin, self).__init__()
    /opt/stack/neutron/neutron/db/db_base_plugin_v2.py(241)__init__()
  -> db.configure_db()
    /opt/stack/neutron/neutron/db/api.py(33)configure_db()
  -> session.get_engine(sqlite_fk=True)
    /opt/stack/neutron/neutron/openstack/common/db/sqlalchemy/session.py(637)get_engine()
  -> mysql_traditional_mode=mysql_traditional_mode)
    /opt/stack/neutron/neutron/openstack/common/db/sqlalchemy/session.py(795)create_engine()
  -> engine.connect()
    /usr/lib/python2.7/dist-packages/sqlalchemy/pool.py(440)<lambda>()
  -> _finalize_fairy(conn, rec, pool, ref, _echo)
    /usr/lib/python2.7/dist-packages/sqlalchemy/pool.py(416)_finalize_fairy()
  -> connection_record.checkin()
    /usr/lib/python2.7/dist-packages/sqlalchemy/pool.py(370)checkin()
  -> pool.dispatch.checkin(connection, self)
    /usr/lib/python2.7/dist-packages/sqlalchemy/event.py(409)__call__()
  -> fn(*args, **kw)
    /opt/stack/neutron/neutron/openstack/common/db/sqlalchemy/session.py(669)_thread_yield()
  -> time.sleep(0)
    /usr/lib/python2.7/dist-packages/eventlet/greenthread.py(31)sleep()
  -> hub.switch()
  > /usr/lib/python2.7/dist-packages/eventlet/hubs/hub.py(177)switch()
  -> import inspect
  (Pdb) 
  
