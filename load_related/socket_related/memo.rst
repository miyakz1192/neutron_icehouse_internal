===========================================================
ソケット系の負荷っぽい事象
===========================================================

TCP/IPサーバがありクライアントがある。
サーバ側の動作が重くて、クライアントがTCP/IPストリームからデータを
読み込んだ時、サーバが何もストリームにデータを置いていないとする。
その時、クライアント側の動作はどうなるか。

正常系の実験
===============

サーバ側の実装
--------------------------

クライアントから接続されると、10バイトの文字列(1234567890)を返す。
pythonで実装されている(server_ok.py)。


クライアント側の実装
----------------------

サーバに接続して、fread(3)を実行する。
1秒に一回 freadを実行する。それを9回実行するその後、close
pythonで実装されている(client.py)。

実験
-----

クライアントからサーバに接続して、10バイトの文字列が正常に帰ってくるかを確認する。

結果::

  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ python client.py 
  size= 10
  1234567890
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ 


問題なし。

異常系の実験1
===============

サーバ側の実装
--------------------------

クライアントが接続してきたら、即座に1234567890を返す。
その後、5秒sleepして、1234567890を返す(server_ng.py)。

クライアント側の実装
----------------------

1秒に一回 freadを実行する。その後、close

実験
-----

以下のようになった。クライアント側のバッファが4096バイトであるため、バッファに
ある程度データが溜まるまでブロッキングして待つらしい。::

  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ python client.py 
  size= 20
  12345678901234567890
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  size= 0
  
  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ 

バッファを5にしてみる。::

  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ python client.py 
  1
  size= 5
  12345
  2
  size= 5
  67890      ★  ここまでで、serverが一回めに返したデータをすべて読み込む（サーバは2回目のデータを返すためにsleep(5sec)中)
  3
  size= 5
  12345     ★  ここで、serverのsleep後、データを返し、bufferサイズ分だけデータがいっぱいになるまで待つ。
  4
  size= 5
  67890     ★　残りのデータを読み込む。(server側はコネクションをclose)
  5
  size= 0
  
  6
  size= 0 　★　clientがreadするがデータはない(serverがcloseしている)
  
  7
  size= 0
  
  8
  size= 0
  
  9
  size= 0
  
  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ 

期待通りになった。


考察
====

read(fread(3))はバッファサイズ分データを読み込む。データがある場合、
いっぱいになるまで待つ（ただし、サーバ側がcloseした時は待ちが
解除される)。

server側がcloseしても、client側のreadがエラーになることは無い。
(0バイトのデータが読み込まれるだけ)

件のhttplibの_safe_read::

 682     def _safe_read(self, amt):                                                  
 683         """Read the number of bytes requested, compensating for partial reads.  
 684                                                                                 
 685         Normally, we have a blocking socket, but a read() can be interrupted    
 686         by a signal (resulting in a partial read).                              
 687                                                                                 
 688         Note that we cannot distinguish between EOF and an interrupt when zero  
 689         bytes have been read. IncompleteRead() will be raised in this           
 690         situation.                                                              
 691                                                                                 
 692         This function should be used when <amt> bytes "should" be present for   
 693         reading. If the bytes are truly not available (due to EOF), then the    
 694         IncompleteRead exception can be used to detect the problem.             
 695         """                                                                     
 696         # NOTE(gps): As of svn r74426 socket._fileobject.read(x) will never     
 697         # return less than x bytes unless EOF is encountered.  It now handles   
 698         # signal interruptions (socket.error EINTR) internally.  This code      
 699         # never caught that exception anyways.  It seems largely pointless.     
 700         # self.fp.read(amt) will work fine.                                     
 701         s = []                                                                  
 702         while amt > 0:                                                          
 703             chunk = self.fp.read(min(amt, MAXAMOUNT))                           
 704             if not chunk:                                                       
 705                 raise IncompleteRead(''.join(s), amt)                           
 706             s.append(chunk)                                                     
 707             amt -= len(chunk)                                                   
 708         return ''.join(s)   

なお、self.fp.readの延長のsocket._fileobjectの延長で呼ばれる以下のコード(/usr/lib/python2.7/socket.py)::

  340     def read(self, size=-1):                                                    
  341         # Use max, disallow tiny reads in a loop as they are very inefficient.  
  342         # We never leave read() with any leftover data from a new recv() call   
  343         # in our internal buffer.                                               
  344         rbufsize = max(self._rbufsize, self.default_bufsize)                    
  345         # Our use of StringIO rather than lists of string objects returned by   
  346         # recv() minimizes memory usage and fragmentation that occurs when      
  347         # rbufsize is large compared to the typical return value of recv().     
  348         buf = self._rbuf                                                        
  349         buf.seek(0, 2)  # seek end          
  (snip)
  364         else:                                                                   
  365             # Read until size bytes or EOF seen, whichever comes first          
  366             buf_len = buf.tell()                                                
  367             if buf_len >= size:                                                 
  368                 # Already have size bytes in our buffer?  Extract and return.   
  369                 buf.seek(0)                                                     
  370                 rv = buf.read(size)                                             
  371                 self._rbuf = StringIO()                                         
  372                 self._rbuf.write(buf.read())                                    
  373                 return rv                                                       
  374                                                                                 
  375             self._rbuf = StringIO()  # reset _rbuf.  we consume it via buf.     
  376             while True:                                                         
  377                 left = size - buf_len                                           
  378                 # recv() will malloc the amount of memory given as its          
  379                 # parameter even though it often returns much less data         
  380                 # than that.  The returned data string is short lived           
  381                 # as we copy it into a StringIO and free it.  This avoids       
  382                 # fragmentation issues on many platforms.                       
  383                 try:                                                            
  384                     data = self._sock.recv(left)  
  

こいつはpdbで表示させると以下のようになる。::

  (Pdb) p self._sock
  <socket object, fd=3, family=2, type=1, protocol=0>
  (Pdb) import inspect
  (Pdb) inspect.getsource(self._sock)
  *** TypeError: <socket object, fd=3, family=2, type=1, protocol=0> is not a module, class, method, function, traceback, frame, or code object
  (Pdb) inspect.getsource(self._sock)
  *** TypeError: <socket object, fd=3, family=2, type=1, protocol=0> is not a module, class, method, function, traceback, frame, or code object
  (Pdb) inspect.getfile(self._sock)
  *** TypeError: <socket object, fd=3, family=2, type=1, protocol=0> is not a module, class, method, function, traceback, frame, or code object
  (Pdb) n

要するにOSレベルのsocketのfread関数であろう。
というも、結局_fileobject.readはfread(2)のラッパーだからだ。::
  http://docs.python.jp/2/library/stdtypes.html#bltin-file-objects

fread(2)って、サーバが何も返さない時は、何を返す？freadじゃないが、readで試してみた。::

  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ ./client 
  char from 1 server = 1234567890,read_len=10,bufsize=128
  sleep 1 sec
  char from 2 server = 1234567890,read_len=10,bufsize=128
  miyakz@lily:~/github_repos/neutron_icehouse_internal/load_related/socket_related$ 

二回めのreadでserverのsleep 5より短い1にしたが、サーバからのデータ返却を待っていた。

IncompleteReadエラーが返る条件。

1. データの読込中にserverがcloseした。
2. クライアント側がタイムアウトした
   →  urllibはOpenタイムアウトしか設定できない。read中は無限待ちとなる(serverがコネクションを
      閉じない限りは)。
3. どこかでclient側のreadがnon blockingに設定されていた？

3.non blocking?
--------------------

自分の環境でgrepしてみたよ::

  miyakz@lily:/usr/lib/python2.7$ grep -rn setblocking *
  asyncore.py:244:            sock.setblocking(0)
  asyncore.py:298:        sock.setblocking(0)
  バイナリファイル asyncore.pyc に一致しました
  バイナリファイル dist-packages/OpenSSL/test/test_ssl.pyc に一致しました
  dist-packages/OpenSSL/test/test_ssl.py:129:    client.setblocking(False)
  dist-packages/OpenSSL/test/test_ssl.py:131:    client.setblocking(True)
  dist-packages/OpenSSL/test/test_ssl.py:143:    server.setblocking(False)
  dist-packages/OpenSSL/test/test_ssl.py:144:    client.setblocking(False)
  dist-packages/OpenSSL/test/test_ssl.py:248:        server.setblocking(True)
  dist-packages/OpenSSL/test/test_ssl.py:249:        client.setblocking(True)
  dist-packages/OpenSSL/test/test_ssl.py:2223:            clientSSL.setblocking(False)
  dist-packages/OpenSSL/test/test_ssl.py:3166:#         server.setblocking(False)
  dist-packages/OpenSSL/test/test_ssl.py:3167:#         client.setblocking(False)
  バイナリファイル dist-packages/OpenSSL/tsafe.pyc に一致しました
  dist-packages/OpenSSL/tsafe.py:16:              'setblocking', 'fileno', 'shutdown', 'close', 'get_cipher_list',
  バイナリファイル dist-packages/axi/indexer.pyc に一致しました
  dist-packages/axi/indexer.py:295:        self.sock.setblocking(False)
  バイナリファイル dist-packages/ndg/httpsclient/ssl_socket.pyc に一致しました
  dist-packages/ndg/httpsclient/ssl_socket.py:185:    def setblocking(self, mode):
  dist-packages/ndg/httpsclient/ssl_socket.py:191:        self.__ssl_conn.setblocking(mode)
  バイナリファイル dist-packages/twisted/test/test_tcp_internals.pyc に一致しました
  dist-packages/twisted/test/test_tcp_internals.py:89:        client.setblocking(False)
  dist-packages/twisted/internet/test/test_socket.py:118:        portSocket.setblocking(False)
  dist-packages/twisted/internet/test/test_socket.py:231:        portSocket.setblocking(False)
  dist-packages/twisted/internet/test/test_unix.py:420:        probeServer.setblocking(False)
  dist-packages/twisted/internet/test/test_udp.py:438:            portSock.setblocking(False)
  バイナリファイル dist-packages/twisted/internet/test/test_socket.pyc に一致しました
  バイナリファイル dist-packages/twisted/internet/test/test_iocp.pyc に一致しました
  バイナリファイル dist-packages/twisted/internet/test/test_udp.pyc に一致しました
  dist-packages/twisted/internet/test/test_iocp.py:54:        client.setblocking(False)
  dist-packages/twisted/internet/test/test_fdset.py:32:            client.setblocking(False)
  dist-packages/twisted/internet/test/test_tcp.py:130:    def setblocking(self, blocking):
  dist-packages/twisted/internet/test/test_tcp.py:188:        skt.setblocking(0)
  dist-packages/twisted/internet/test/test_tcp.py:989:            portSock.setblocking(False)
  dist-packages/twisted/internet/test/test_tcp.py:1100:        client.setblocking(False)
  dist-packages/twisted/internet/test/test_tcp.py:1183:        client.setblocking(False)
  バイナリファイル dist-packages/twisted/internet/test/test_tcp.pyc に一致しました
  バイナリファイル dist-packages/twisted/internet/test/test_unix.pyc に一致しました
  バイナリファイル dist-packages/twisted/internet/test/test_fdset.pyc に一致しました
  dist-packages/twisted/internet/base.py:1111:        s.setblocking(0)
  dist-packages/twisted/internet/posixbase.py:83:        client.setblocking(0)
  dist-packages/twisted/internet/posixbase.py:84:        reader.setblocking(0)
  バイナリファイル dist-packages/twisted/internet/posixbase.pyc に一致しました
  バイナリファイル dist-packages/twisted/internet/tcp.pyc に一致しました
  dist-packages/twisted/internet/tcp.py:183:        self.socket.setblocking(0)
  dist-packages/twisted/internet/tcp.py:531:        s.setblocking(0)
  バイナリファイル dist-packages/twisted/internet/base.pyc に一致しました
  dist-packages/twisted/internet/interfaces.py:911:        portSocket.setblocking(False)
  バイナリファイル dist-packages/twisted/internet/interfaces.pyc に一致しました
  dist-packages/twisted/python/test/test_sendmsg.py:310:        self.input.setblocking(False)
  バイナリファイル dist-packages/twisted/python/test/test_sendmsg.pyc に一致しました
  バイナリファイル multiprocessing/connection.pyc に一致しました
  multiprocessing/connection.py:189:            s1.setblocking(True)
  multiprocessing/connection.py:190:            s2.setblocking(True)
  multiprocessing/connection.py:255:            self._socket.setblocking(True)
  multiprocessing/connection.py:281:        s.setblocking(True)
  multiprocessing/connection.py:306:        s.setblocking(True)
  socket.py:157:    'sendall', 'setblocking',
  バイナリファイル socket.pyc に一致しました
  miyakz@lily:/usr/lib/python2.7$ 

eventletでは以下。::

  miyakz@lily:~/sources/eventlet$ grep -rn setblocking *
  eventlet/green/ssl.py:96:    def setblocking(self, flag):
  eventlet/green/subprocess.py:46:    # setblocking() method, and the Python fcntl module doesn't exist on
  eventlet/greenio/base.py:79:        setblocking = fd.setblocking
  eventlet/greenio/base.py:81:        # fd has no setblocking() method. It could be that this version of
  eventlet/greenio/base.py:82:        # Python predates socket.setblocking(). In that case, we can still set
  eventlet/greenio/base.py:89:            # at all, but rather a file-like object with no setblocking()
  eventlet/greenio/base.py:94:                                      "with no setblocking() method "
  eventlet/greenio/base.py:103:        # socket supports setblocking()
  eventlet/greenio/base.py:104:        setblocking(0)
  eventlet/greenio/base.py:144:        # when client calls setblocking(0) or settimeout(0) the socket must
  eventlet/greenio/base.py:386:    def setblocking(self, flag):
  eventlet/greenio/base.py:396:            self.setblocking(True)
  eventlet/tags:1060:setblocking  green/ssl.py  /^    def setblocking(self, flag):$/;"  m class:GreenSSLSocket
  eventlet/tags:1061:setblocking  greenio/base.py /^    def setblocking(self, flag):$/;"  m class:GreenSocket
  tags:1966:setblocking eventlet/green/ssl.py /^    def setblocking(self, flag):$/;"  m class:GreenSSLSocket
  tags:1967:setblocking eventlet/greenio/base.py  /^    def setblocking(self, flag):$/;"  m class:GreenSocket
  miyakz@lily:~/sources/eventlet$ 
  




